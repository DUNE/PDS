#include <bit>
#include <type_traits>
#include <hdf5.h>
#include "daqdataformats/FragmentHeader.hpp"
#include "fddetdataformats/DAPHNEEthFrame.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

using Frame = dunedaq::fddetdataformats::DAPHNEEthFrame;
using Header = dunedaq::daqdataformats::FragmentHeader;
using Clock = std::chrono::steady_clock;
static_assert(sizeof(Frame) == 512 && Frame::s_num_adcs == 256);
static_assert(sizeof(Header) == 72 && std::endian::native == std::endian::little);

struct Handle {
  hid_t id;
  herr_t (*close)(hid_t);
  Handle(hid_t value, herr_t (*closer)(hid_t)) : id(value), close(closer) {
    if (id < 0) throw std::runtime_error("Cannot open HDF5 object");
  }
  Handle(const Handle&) = delete;
  ~Handle() { close(id); }
  operator hid_t() const { return id; }
};

double elapsed(Clock::time_point start) {
  return std::chrono::duration<double>(Clock::now() - start).count();
}

std::string quote(const std::string& value) {
  std::string result = "\"";
  const char* hex = "0123456789abcdef";
  for (unsigned char c : value) {
    if (c == '"' || c == '\\') result += '\\';
    if (c < 32) {
      result += "\\u00";
      result += hex[c >> 4]; result += hex[c & 15];
    } else result += static_cast<char>(c);
  }
  return result + '"';
}

struct Datasets { std::vector<std::string> paths; bool failed = false; };
herr_t visit(hid_t, const char* name, const H5O_info_t* info, void* arg) {
  auto& datasets = *static_cast<Datasets*>(arg);
  try {
    if (info->type == H5O_TYPE_DATASET) datasets.paths.emplace_back(name);
    return 0;
  } catch (...) { datasets.failed = true; return -1; }
}

void read_bytes(hid_t dataset, hid_t type, hid_t space, int rank,
                hsize_t offset, hsize_t count, void* output) {
  hsize_t start[2] = {offset, 0}, extent[2] = {count, 1};
  if (rank < 1 || rank > 2 || H5Sselect_hyperslab(space, H5S_SELECT_SET, start, nullptr, extent, nullptr) < 0)
    throw std::runtime_error("Cannot select HDF5 byte range");
  Handle memory(H5Screate_simple(1, &count, nullptr), H5Sclose);
  // Use the stored byte type: converting signed int8 to uint8 would clamp data.
  if (H5Dread(dataset, type, memory, space, H5P_DEFAULT, output) < 0)
    throw std::runtime_error("Cannot read HDF5 byte range");
}

std::ofstream output(const std::filesystem::path& path) {
  std::ofstream file;
  file.exceptions(std::ios::failbit | std::ios::badbit);
  file.open(path, std::ios::binary);
  return file;
}

template<typename T>
void write(std::ofstream& file, const std::vector<T>& values) {
  file.write(reinterpret_cast<const char*>(values.data()), values.size() * sizeof(T));
}

int main(int argc, char** argv) {
  if (argc != 3) {
    std::cerr << "Usage: pds-hdf5-unpack INPUT.hdf5 NEW_OUTPUT_DIR\n";
    return 2;
  }
  try {
    const auto start = Clock::now();
    const std::filesystem::path directory(argv[2]);
    Handle input(H5Fopen(argv[1], H5F_ACC_RDONLY, H5P_DEFAULT), H5Fclose);
    Datasets datasets;
    if (H5Ovisit(input, H5_INDEX_NAME, H5_ITER_INC, visit, &datasets) < 0 || datasets.failed)
      throw std::runtime_error("Cannot enumerate HDF5 datasets");
    if (!std::filesystem::create_directory(directory))
      throw std::runtime_error("Output directory already exists");
    auto adc = output(directory / "adc.u16.bin");
    auto timestamps = output(directory / "timestamp.u64.bin");
    auto channels = output(directory / "channel.u8.bin");
    auto headers = output(directory / "header.u8.bin");
    auto manifest = output(directory / "manifest.json");
    manifest << "{\"schema\":\"pds.daphne.v4.arrays.v1\",\"input\":" << quote(argv[1])
             << ",\"samples_per_waveform\":256,\"adc_bits\":14,\"adc_dtype\":\"<u2\",\"frame_bytes\":512,\"header_bytes\":64,\"byte_order\":\"little\",\"fragment_header_version\":6,\"fragments\":[";
    uint64_t rows = 0, fragments = 0, empty = 0, flagged = 0;
    uint64_t minimum_timestamp = std::numeric_limits<uint64_t>::max(), maximum_timestamp = 0;
    uint16_t minimum_adc = 16383, maximum_adc = 0;
    std::array<uint64_t, 32> channel_counts{};
    std::array<uint64_t, 4> tag_counts{};
    double read_seconds = 0, decode_seconds = 0, write_seconds = 0;
    for (const auto& path : datasets.paths) {
      Handle dataset(H5Dopen2(input, path.c_str(), H5P_DEFAULT), H5Dclose);
      Handle type(H5Dget_type(dataset), H5Tclose);
      if (H5Tget_class(type) != H5T_INTEGER || H5Tget_size(type) != 1) continue;
      Handle space(H5Dget_space(dataset), H5Sclose);
      const int rank = H5Sget_simple_extent_ndims(space);
      hsize_t dimensions[2]{};
      if (rank < 1 || rank > 2) throw std::runtime_error("Unsupported byte dataset rank: " + path);
      H5Sget_simple_extent_dims(space, dimensions, nullptr);
      if (rank == 2 && dimensions[1] != 1) throw std::runtime_error("Unsupported byte dataset shape: " + path);
      if (dimensions[0] < sizeof(Header)) continue;
      Header header;
      auto mark = Clock::now();
      read_bytes(dataset, type, space, rank, 0, sizeof(header), &header);
      read_seconds += elapsed(mark);
      if (header.fragment_header_marker != Header::s_fragment_header_marker) continue;
      if (header.fragment_type != static_cast<uint32_t>(dunedaq::daqdataformats::FragmentType::kDAPHNEEth)) continue;
      if (header.version != Header::s_fragment_header_version || header.size != dimensions[0])
        throw std::runtime_error("Unsupported or inconsistent fragment header: " + path);
      const uint64_t payload = header.size - sizeof(Header);
      if (payload % sizeof(Frame)) throw std::runtime_error("Truncated DAPHNE frame: " + path);
      const uint64_t count = payload / sizeof(Frame);
      if (fragments++) manifest << ',';
      manifest << "{\"dataset\":" << quote(path) << ",\"first_row\":" << rows << ",\"rows\":" << count
               << ",\"source_id\":" << header.element_id.id << ",\"run_number\":" << header.run_number
               << ",\"trigger_number\":" << header.trigger_number << ",\"sequence_number\":" << header.sequence_number
               << ",\"status_bits\":" << header.status_bits << ",\"window_begin\":" << header.window_begin
               << ",\"window_end\":" << header.window_end << '}';
      empty += count == 0;
      flagged += header.status_bits != 0;
      for (uint64_t offset = 0; offset < count;) {
        const auto batch = std::min<uint64_t>(count - offset, 8192);
        std::vector<Frame> frames(batch);
        mark = Clock::now();
        read_bytes(dataset, type, space, rank, sizeof(Header) + offset * sizeof(Frame), batch * sizeof(Frame), frames.data());
        read_seconds += elapsed(mark);
        std::vector<uint16_t> values(batch * Frame::s_num_adcs);
        std::vector<uint64_t> ticks(batch);
        std::vector<uint8_t> ids(batch), frame_headers(batch * 64);
        mark = Clock::now();
        for (size_t i = 0; i < batch; ++i) {
          const auto& frame = frames[i];
          const auto channel = frame.get_channel();
          if (frame.header.version != 4 || frame.daq_header.block_length != 63 || channel >= 32 || frame.daq_header.stream_id != channel / 8)
            throw std::runtime_error("Unsupported DAPHNE waveform: " + path);
          ticks[i] = frame.get_timestamp(); ids[i] = channel;
          std::memcpy(frame_headers.data() + i * 64, &frame, 64);
          ++channel_counts[channel]; ++tag_counts[frame.header.calibration_tag];
          minimum_timestamp = std::min(minimum_timestamp, ticks[i]); maximum_timestamp = std::max(maximum_timestamp, ticks[i]);
          // Same shared frame accessor used by rawdatautils; no duplicate bit decoder.
          for (int sample = 0; sample < Frame::s_num_adcs; ++sample) {
            const auto value = frame.get_adc(sample);
            values[i * Frame::s_num_adcs + sample] = value;
            minimum_adc = std::min(minimum_adc, value); maximum_adc = std::max(maximum_adc, value);
          }
        }
        decode_seconds += elapsed(mark);
        mark = Clock::now();
        write(adc, values); write(timestamps, ticks); write(channels, ids); write(headers, frame_headers);
        write_seconds += elapsed(mark);
        rows += batch; offset += batch;
      }
    }
    if (!rows) throw std::runtime_error("No DAPHNE v4 waveforms found");
    auto mark = Clock::now();
    adc.close(); timestamps.close(); channels.close(); headers.close();
    write_seconds += elapsed(mark);
    manifest << "],\"complete\":true,\"waveforms\":" << rows << ",\"channels\":{";
    bool first = true;
    for (size_t channel = 0; channel < channel_counts.size(); ++channel) {
      if (!channel_counts[channel]) continue;
      if (!first) manifest << ',';
      first = false; manifest << quote(std::to_string(channel)) << ':' << channel_counts[channel];
    }
    manifest << "},\"calibration_tags\":[" << tag_counts[0] << ',' << tag_counts[1] << ',' << tag_counts[2] << ',' << tag_counts[3]
             << "],\"empty_fragments\":" << empty << ",\"flagged_fragments\":" << flagged
             << ",\"adc_min\":" << minimum_adc << ",\"adc_max\":" << maximum_adc
             << ",\"timestamp_min\":" << minimum_timestamp << ",\"timestamp_max\":" << maximum_timestamp << "}\n";
    manifest.close();
    std::cout << std::setprecision(9) << "{\"waveforms\":" << rows << ",\"samples\":" << rows * Frame::s_num_adcs
              << ",\"fragments\":" << fragments << ",\"flagged_fragments\":" << flagged
              << ",\"read_seconds\":" << read_seconds << ",\"decode_seconds\":" << decode_seconds
              << ",\"write_seconds\":" << write_seconds << ",\"total_seconds\":" << elapsed(start) << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
