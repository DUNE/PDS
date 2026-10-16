library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.daphne_subsystem_pkg.all;
use work.grouped_frame_pkg.all;

entity afe_grouped_selftrigger_island is
  generic (
    CHANNELS_PER_AFE_G : positive := 8;
    CHANNEL_ID_BASE_G  : natural  := 0
  );
  port (
    clock_i             : in  std_logic;
    reset_i             : in  std_logic;
    builder_clock_i, builder_reset_i : in std_logic;
    reset_st_counters_i : in  std_logic;
    timestamp_i         : in  std_logic_vector(63 downto 0);
    version_i           : in  std_logic_vector(3 downto 0);
    signal_delay_i      : in  std_logic_vector(4 downto 0);
    descriptor_config_i : in  std_logic_vector(13 downto 0);
    calibration_mask_i : in std_logic_vector(CHANNELS_PER_AFE_G-1 downto 0) := (others=>'0');
    pause_mask_i : in std_logic_vector(CHANNELS_PER_AFE_G-1 downto 0) := (others=>'0');
    pause_applied_o, drained_o : out std_logic_vector(CHANNELS_PER_AFE_G-1 downto 0);
    calibration_applied_o : out std_logic_vector(CHANNELS_PER_AFE_G-1 downto 0);
    force_trigger_i     : in  std_logic;
    self_trigger_enable_i : in std_logic := '1';
    timing_trigger_enable_i : in std_logic := '1';
    trigger_inhibit_i : in std_logic := '0';
    force_calibration_tag_i : in std_logic_vector(1 downto 0);
    din_i               : in  sample14_array_t(0 to CHANNELS_PER_AFE_G - 1);
    trigger_control_i   : in  trigger_xcorr_control_array_t(0 to CHANNELS_PER_AFE_G - 1);
    trigger_result_o    : out trigger_xcorr_result_array_t(0 to CHANNELS_PER_AFE_G - 1);
    descriptor_result_o : out peak_descriptor_result_array_t(0 to CHANNELS_PER_AFE_G - 1);
    record_count_o      : out slv64_array_t(0 to CHANNELS_PER_AFE_G - 1);
    full_count_o        : out slv64_array_t(0 to CHANNELS_PER_AFE_G - 1);
    busy_count_o        : out slv64_array_t(0 to CHANNELS_PER_AFE_G - 1);
    trigger_count_o     : out slv64_array_t(0 to CHANNELS_PER_AFE_G - 1);
    packet_count_o      : out slv64_array_t(0 to CHANNELS_PER_AFE_G - 1);
    continuation_count_o      : out slv64_array_t(0 to CHANNELS_PER_AFE_G - 1);
    continuation_drop_count_o      : out slv64_array_t(0 to CHANNELS_PER_AFE_G - 1);
    covered_trigger_count_o      : out slv64_array_t(0 to CHANNELS_PER_AFE_G - 1);
    descriptor_overflow_count_o      : out slv64_array_t(0 to CHANNELS_PER_AFE_G - 1);
    delayed_sample_o    : out sample14_array_t(0 to CHANNELS_PER_AFE_G - 1);
    ready_o             : out std_logic_array_t(0 to CHANNELS_PER_AFE_G - 1);
    rd_en_i             : in  std_logic_array_t(0 to CHANNELS_PER_AFE_G - 1);
    dout_o              : out slv72_array_t(0 to CHANNELS_PER_AFE_G - 1)
  );
end entity afe_grouped_selftrigger_island;

architecture rtl of afe_grouped_selftrigger_island is
  signal gated_control_s : trigger_xcorr_control_array_t(0 to CHANNELS_PER_AFE_G-1);
  signal admission_s, self_enable_s, timing_enable_s, force_trigger_s : std_logic_vector(CHANNELS_PER_AFE_G-1 downto 0);
  signal pause_applied_s, drained_s : std_logic_vector(CHANNELS_PER_AFE_G-1 downto 0);
  signal readout_enable_s : std_logic_array_t(0 to CHANNELS_PER_AFE_G - 1);
  signal descriptor_control_s : peak_descriptor_control_array_t(0 to CHANNELS_PER_AFE_G - 1);
  signal trigger_result_s     : trigger_xcorr_result_array_t(0 to CHANNELS_PER_AFE_G - 1);
  signal descriptor_result_s  : peak_descriptor_result_array_t(0 to CHANNELS_PER_AFE_G - 1);
  signal descriptor_trailer_s : peak_descriptor_trailer_bank_t(0 to CHANNELS_PER_AFE_G - 1);
  signal frame_match_s        : std_logic_array_t(0 to CHANNELS_PER_AFE_G - 1);
  signal desc_s : grouped_descriptor_array_t(0 to CHANNELS_PER_AFE_G-1);
  signal desc_valid_s, desc_busy_s, packet_wr_s, packet_commit_s : std_logic_array_t(0 to CHANNELS_PER_AFE_G-1);
  signal ring_addr_s : ring_address_array_t(0 to CHANNELS_PER_AFE_G-1);
  signal ring_data_s : sample14_array_t(0 to CHANNELS_PER_AFE_G-1);
  type addr_array_t is array(natural range <>) of unsigned(11 downto 0);
  signal packet_addr_s : addr_array_t(0 to CHANNELS_PER_AFE_G/4-1);
  signal packet_data_s : slv72_array_t(0 to CHANNELS_PER_AFE_G/4-1);
  signal packet_overflow_s : std_logic_array_t(0 to CHANNELS_PER_AFE_G/4-1);
begin
  calibration_policy_inst : entity work.channel_calibration_policy
    generic map(CHANNEL_COUNT_G=>CHANNELS_PER_AFE_G)
    port map(clock_i=>clock_i, reset_i=>reset_i, calibration_mask_i=>calibration_mask_i, pause_mask_i=>pause_mask_i,
      self_enable_i=>self_trigger_enable_i, timing_enable_i=>timing_trigger_enable_i,
      force_trigger_i=>force_trigger_i, inhibit_i=>trigger_inhibit_i,
      admission_o=>admission_s, self_enable_o=>self_enable_s, timing_enable_o=>timing_enable_s,
      force_trigger_o=>force_trigger_s, applied_mask_o=>calibration_applied_o, pause_applied_o=>pause_applied_s);
  pause_applied_o <= pause_applied_s;
  drained_o <= drained_s and pause_applied_s and pause_mask_i;
  gate_timing : process(all)
  begin
    gated_control_s <= trigger_control_i;
    for ch in 0 to CHANNELS_PER_AFE_G-1 loop
      gated_control_s(ch).ti_trigger_stbr <= trigger_control_i(ch).ti_trigger_stbr and timing_enable_s(ch);
    end loop;
  end process;
  assert CHANNELS_PER_AFE_G=8 report "production grouped island requires eight channels" severity failure;
  gen_builder : for group_idx in 0 to CHANNELS_PER_AFE_G/4-1 generate
    constant B : natural := group_idx*4;
  begin
    grouped_serializer_inst : entity work.afe_stc3_stream_serializer
      port map(clock_i=>clock_i, reset_i=>reset_i,
        builder_clock_i=>builder_clock_i, builder_reset_i=>builder_reset_i,
        desc_i=>desc_s(B to B+3), desc_valid_i=>desc_valid_s(B to B+3),
        desc_busy_o=>desc_busy_s(B to B+3), ring_rd_addr_o=>ring_addr_s(B to B+3),
        ring_data_i=>ring_data_s(B to B+3), packet_wr_o=>packet_wr_s(B to B+3),
        packet_commit_o=>packet_commit_s(B to B+3), packet_addr_o=>packet_addr_s(group_idx),
        packet_data_o=>packet_data_s(group_idx), packet_overflow_o=>packet_overflow_s(group_idx));
  end generate;
  trigger_bank_inst : entity work.afe_trigger_bank
    generic map (
      CHANNEL_COUNT_G => CHANNELS_PER_AFE_G
    )
    port map (
      clock_i              => clock_i,
      reset_i              => reset_i,
      timestamp_i          => timestamp_i,
      din_i                => din_i,
      trigger_control_i    => gated_control_s,
      descriptor_control_i => descriptor_control_s,
      trigger_result_o     => trigger_result_s,
      descriptor_result_o  => descriptor_result_s,
      descriptor_trailer_o => descriptor_trailer_s
    );

  gen_channel : for idx in 0 to CHANNELS_PER_AFE_G - 1 generate
    constant CHANNEL_ID_C : std_logic_vector(7 downto 0) :=
      std_logic_vector(to_unsigned(CHANNEL_ID_BASE_G + idx, 8));
  begin
    readout_enable_s(idx) <= trigger_result_s(idx).enabled and admission_s(idx);
    descriptor_control_s(idx).config <= descriptor_config_i;
    descriptor_control_s(idx).frame_match <= frame_match_s(idx);

    record_builder_inst : entity work.stc3_frame_source
      port map (
        ch_id_i             => CHANNEL_ID_C,
        builder_clock_i=>builder_clock_i, desc_o=>desc_s(idx), desc_valid_o=>desc_valid_s(idx),
        desc_busy_i=>desc_busy_s(idx), ring_rd_addr_i=>ring_addr_s(idx), ring_data_o=>ring_data_s(idx),
        packet_wr_i=>packet_wr_s(idx), packet_commit_i=>packet_commit_s(idx),
        packet_addr_i=>packet_addr_s(idx/4), packet_data_i=>packet_data_s(idx/4),
        packet_overflow_i=>packet_overflow_s(idx/4),
        version_i           => version_i,
        threshold_xc_i      => trigger_control_i(idx).threshold_xc,
        signal_delay_i      => signal_delay_i,
        continuation_enable_i => trigger_control_i(idx).continuation_config(31) and not calibration_mask_i(idx),
        positive_pulse_i    => trigger_control_i(idx).invert_enable,
        activity_threshold_i => trigger_control_i(idx).continuation_config(13 downto 0),
        quiet_samples_i     => trigger_control_i(idx).continuation_config(24 downto 16),
        clock_i             => clock_i,
        reset_i             => reset_i,
        reset_st_counters_i => reset_st_counters_i,
	        enable_i            => readout_enable_s(idx),
        self_trigger_enable_i => self_enable_s(idx),
        timing_trigger_enable_i => timing_enable_s(idx),
	        force_trigger_i     => force_trigger_s(idx),
	        force_calibration_tag_i => force_calibration_tag_i,
	        timestamp_i         => timestamp_i,
        din_i               => din_i(idx),
        trigger_i           => trigger_result_s(idx),
        trailer_capture_i   => descriptor_result_s(idx).trailer_available,
        trailer_i           => descriptor_trailer_s(idx),
        frame_match_o       => frame_match_s(idx),
        record_count_o      => record_count_o(idx),
        full_count_o        => full_count_o(idx),
        busy_count_o        => busy_count_o(idx),
        spacing_reject_count_o => open,
        queue_reject_count_o   => open,
        ring_reject_count_o    => open,
        output_reject_count_o  => open,
        trigger_count_o     => trigger_count_o(idx),
        packet_count_o      => packet_count_o(idx),
        continuation_count_o      => continuation_count_o(idx),
        continuation_drop_count_o      => continuation_drop_count_o(idx),
        covered_trigger_count_o      => covered_trigger_count_o(idx),
        descriptor_overflow_count_o      => descriptor_overflow_count_o(idx),
        delayed_sample_o    => delayed_sample_o(idx),
        drained_o           => drained_s(idx),
        ready_o             => ready_o(idx),
        rd_en_i             => rd_en_i(idx),
        dout_o              => dout_o(idx)
      );
  end generate gen_channel;

  trigger_result_o    <= trigger_result_s;
  descriptor_result_o <= descriptor_result_s;
end architecture rtl;
