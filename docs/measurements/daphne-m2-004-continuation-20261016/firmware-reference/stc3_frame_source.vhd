library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.daphne_subsystem_pkg.all;
use work.grouped_frame_pkg.all;

entity stc3_frame_source is
  port (
    ch_id_i                  : in  std_logic_vector(7 downto 0);
    version_i                : in  std_logic_vector(3 downto 0);
    threshold_xc_i           : in  std_logic_vector(27 downto 0);
    signal_delay_i           : in  std_logic_vector(4 downto 0);
    clock_i                  : in  std_logic;
    reset_i                  : in  std_logic;
    reset_st_counters_i      : in  std_logic;
    enable_i                 : in  std_logic;
    force_trigger_i          : in  std_logic;
    self_trigger_enable_i    : in std_logic := '1';
    timing_trigger_enable_i  : in std_logic := '1';
    force_calibration_tag_i  : in  std_logic_vector(1 downto 0);
    timestamp_i              : in  std_logic_vector(63 downto 0);
    din_i                    : in  std_logic_vector(13 downto 0);
    trigger_i                : in  trigger_xcorr_result_t;
    continuation_enable_i    : in std_logic := '1';
    positive_pulse_i         : in std_logic := '0';
    activity_threshold_i     : in std_logic_vector(13 downto 0) := "00000001000000";
    quiet_samples_i          : in std_logic_vector(8 downto 0) := "000100000";
    continuation_count_o     : out std_logic_vector(63 downto 0);
    continuation_drop_count_o : out std_logic_vector(63 downto 0);
    covered_trigger_count_o  : out std_logic_vector(63 downto 0);
    descriptor_overflow_count_o : out std_logic_vector(63 downto 0);
    trailer_capture_i        : in  std_logic;
    trailer_i                : in  peak_descriptor_trailer_t;
    frame_match_o            : out std_logic;
    record_count_o           : out std_logic_vector(63 downto 0);
    full_count_o             : out std_logic_vector(63 downto 0);
    busy_count_o             : out std_logic_vector(63 downto 0);
    spacing_reject_count_o   : out std_logic_vector(63 downto 0);
    queue_reject_count_o     : out std_logic_vector(63 downto 0);
    ring_reject_count_o      : out std_logic_vector(63 downto 0);
    output_reject_count_o    : out std_logic_vector(63 downto 0);
    trigger_count_o          : out std_logic_vector(63 downto 0);
    packet_count_o           : out std_logic_vector(63 downto 0);
    delayed_sample_o         : out std_logic_vector(13 downto 0);
    builder_clock_i          : in std_logic;
    desc_o                   : out grouped_descriptor_t;
    desc_valid_o             : out std_logic;
    desc_busy_i              : in std_logic;
    ring_rd_addr_i           : in unsigned(10 downto 0);
    ring_data_o              : out std_logic_vector(13 downto 0);
    packet_wr_i              : in std_logic;
    packet_addr_i            : in unsigned(11 downto 0);
    packet_data_i            : in std_logic_vector(71 downto 0);
    packet_commit_i          : in std_logic;
    packet_overflow_i        : in std_logic;
    drained_o : out std_logic;
    ready_o                  : out std_logic;
    rd_en_i                  : in  std_logic;
    dout_o                   : out std_logic_vector(71 downto 0)
  );
end entity stc3_frame_source;

-- ADC-domain continuation admission, sample history and reserved packet slots.
-- The shared engine owns the queue head until the final header reaches this
-- clock domain. Publication and queue release occur on that same commit edge.
architecture rtl of stc3_frame_source is
  constant FRAME_SAMPLE_COUNT_C : natural := 256;
  constant POSTTRIGGER_SAMPLES_C : natural := 447;
  constant PRETRIGGER_SAMPLES_C : natural := 64;
  constant FRAME_WORD_COUNT_C : natural := 63;
  constant RING_DEPTH_C : positive := 2048;
  constant FRAME_QUEUE_DEPTH_C : positive := 4;
  constant PACKET_SLOT_COUNT_C : positive := 32;
  constant SERIALIZER_CYCLES_C : positive := 512;
  constant RETENTION_LIMIT_C : positive := RING_DEPTH_C - 64;
  -- Live ring/queue references span at most 2048 samples. The extra two
  -- address bits give an 8192-sample modulo and a 4096-sample signed half-range.
  -- Expired spacing references are invalidated and deadlines are clamped below.
  subtype sample_seq_t is unsigned(12 downto 0);
  subtype slot_t is unsigned(4 downto 0);
  type frame_meta_t is record
    start_seq : sample_seq_t;
    sample0_ts : std_logic_vector(63 downto 0);
    baseline : std_logic_vector(13 downto 0);
    trigger_sample : std_logic_vector(13 downto 0);
    threshold_lsb : std_logic_vector(13 downto 0);
    activity_threshold : std_logic_vector(13 downto 0);
    positive_pulse : std_logic;
    calibration_tag : std_logic_vector(1 downto 0);
    continuation : std_logic;
    slot : slot_t;
  end record;
  constant META_NULL_C : frame_meta_t := (
    start_seq=>(others=>'0'), sample0_ts=>(others=>'0'), baseline=>(others=>'0'),
    trigger_sample=>(others=>'0'), threshold_lsb=>(others=>'0'),
    activity_threshold=>(others=>'0'), positive_pulse=>'0', calibration_tag=>CALIBRATION_TAG_NORMAL_C,
    continuation=>'0', slot=>(others=>'0'));
  -- A packed, single-write distributed RAM avoids per-field register feedback
  -- and reset muxes across the descriptor queue. Empty entries are never used.
  subtype packed_meta_t is std_logic_vector(141 downto 0);
  type frame_queue_t is array(0 to FRAME_QUEUE_DEPTH_C-1) of packed_meta_t;
  function pack_meta(m : frame_meta_t) return packed_meta_t is
  begin
    return std_logic_vector(m.start_seq) & m.sample0_ts & m.baseline & m.trigger_sample &
      m.threshold_lsb & m.activity_threshold & m.positive_pulse & m.calibration_tag &
      m.continuation & std_logic_vector(m.slot);
  end;
  function unpack_meta(v : packed_meta_t) return frame_meta_t is
    variable m : frame_meta_t;
  begin
    m.start_seq:=unsigned(v(141 downto 129)); m.sample0_ts:=v(128 downto 65);
    m.baseline:=v(64 downto 51); m.trigger_sample:=v(50 downto 37);
    m.threshold_lsb:=v(36 downto 23); m.activity_threshold:=v(22 downto 9);
    m.positive_pulse:=v(8); m.calibration_tag:=v(7 downto 6); m.continuation:=v(5);
    m.slot:=unsigned(v(4 downto 0));
    return m;
  end;
  function raw_baseline(value : std_logic_vector(13 downto 0); positive : std_logic) return std_logic_vector is
  begin
    if positive='1' then return std_logic_vector(to_unsigned(0,14)-unsigned(value)); end if;
    return value;
  end;
  function next_q(i : natural) return natural is
  begin return (i+1) mod FRAME_QUEUE_DEPTH_C; end;
  function seq_age(now_seq, start_seq : sample_seq_t) return natural is
    variable d : sample_seq_t;
  begin
    if start_seq = now_seq+1 then return 0; end if;
    d := now_seq-start_seq;
    if d > to_unsigned(RING_DEPTH_C, d'length) then return RING_DEPTH_C+1; end if;
    return to_integer(d);
  end;
  function slot_addr(slot : slot_t; word_idx : natural) return unsigned is
  begin return slot & to_unsigned(word_idx,7); end;
  function inside_window(delta : sample_seq_t;
                         continuation : std_logic) return boolean is
  begin
    -- The union of trigger-in-frame [0,255] and pretrigger-start-in-frame
    -- [64,319] is [0,319]. Call only after the full event-age guard.
    if continuation='1' then return delta<to_unsigned(FRAME_SAMPLE_COUNT_C+PRETRIGGER_SAMPLES_C,sample_seq_t'length); end if;
    return delta<to_unsigned(FRAME_SAMPLE_COUNT_C,sample_seq_t'length);
  end;
  signal seq_s : sample_seq_t := (others=>'0');
  signal history_s : natural range 0 to RING_DEPTH_C := 0;
  signal queue_s : frame_queue_t := (others=>(others=>'0'));
  attribute ram_style : string;
  attribute ram_style of queue_s : signal is "distributed";
  signal head_s, tail_s : natural range 0 to FRAME_QUEUE_DEPTH_C-1 := 0;
  signal queue_count_s : natural range 0 to FRAME_QUEUE_DEPTH_C := 0;
  signal queue_head_s, queue_next_s : frame_meta_t;
  -- Publication is ordered, so slot liveness is represented by pointers and
  -- counts. Only exceptional stale-frame holes need a per-slot bit.
  signal dropped_s : std_logic_vector(PACKET_SLOT_COUNT_C-1 downto 0) := (others=>'0');
  signal publish_drop_s, consume_drop_s : std_logic;
  signal allocate_slot_s, read_slot_s : slot_t := (others=>'0');
  signal reserved_count_s, published_count_s : natural range 0 to PACKET_SLOT_COUNT_C := 0;
  signal read_word_s : natural range 0 to FRAME_WORD_COUNT_C-1 := 0;
  signal store_raddr_s : unsigned(11 downto 0);
  signal activity_baseline_s : std_logic_vector(13 downto 0);
  signal chain_active_s, current_accepted_s, previous_accepted_s : std_logic := '0';
  signal current_s, previous_s : frame_meta_t := META_NULL_C;
  -- Three256-sample windows cover the447-clock maximum tuple latency.
  signal older_start_s : sample_seq_t := (others=>'0');
  signal older_accepted_s : std_logic := '0';
  signal activity_s : std_logic := '0';
  signal quiet_s : natural range 0 to 511 := 0;
  signal chain_quiet_limit_s : natural range 1 to 511 := 32;
  signal required_end_s : sample_seq_t := (others=>'0');
  signal last_start_s : sample_seq_t := (others=>'0');
  signal last_start_valid_s : std_logic := '0';
  signal selected_trigger_pulse_s : std_logic;
  signal event_pulse_s, trigger_previous_s : std_logic := '0';
  signal event_sample0_ts_s : std_logic_vector(63 downto 0);
  -- One full-width age check protects the bounded local comparisons against
  -- stale/future tuples whose low sequence bits would otherwise alias.
  signal event_age_s : unsigned(63 downto 0);
  signal timestamp_previous_s : unsigned(63 downto 0) := (others=>'0');
  signal timestamp_armed_s : std_logic := '0';
  signal timestamp_jump_s : std_logic;
  signal event_seq_s, current_delta_s, previous_delta_s, older_delta_s : sample_seq_t;
  signal event_sample_s : std_logic_vector(13 downto 0);
  signal event_tag_s : std_logic_vector(1 downto 0);
  signal record_count_s, full_count_s, busy_count_s, spacing_count_s, queue_drop_s, ring_drop_s,
         trigger_count_s, packet_count_s, continuation_count_s, continuation_drop_s,
         covered_count_s, descriptor_overflow_count_s : unsigned(31 downto 0) := (others=>'0');
begin
  -- Clock/reset/timestamp are common to all channels, allowing synthesis to
  -- share this epoch guard. Natural64-bit wrap is a normal increment.
  timestamp_jump_s <= '1' when timestamp_armed_s='1' and
    unsigned(timestamp_i)/=timestamp_previous_s+1 else '0';
  -- Place timestamp arithmetic before the channel-specific force selection.
  -- The normal tuple timestamp is shared across board channels, so these
  -- full-width subtractions can share without changing modulo64 semantics.
  event_age_s <= (others=>'0') when force_trigger_i='1' else
                 unsigned(timestamp_i)-unsigned(trigger_i.trigger_timestamp);
  event_sample0_ts_s <= std_logic_vector(unsigned(timestamp_i)-PRETRIGGER_SAMPLES_C)
                         when force_trigger_i='1' else
                       std_logic_vector(unsigned(trigger_i.trigger_timestamp)-PRETRIGGER_SAMPLES_C);
  event_seq_s <= seq_s-resize(event_age_s,sample_seq_t'length);
  current_delta_s <= event_seq_s-current_s.start_seq;
  previous_delta_s <= event_seq_s-previous_s.start_seq;
  older_delta_s <= event_seq_s-older_start_s;
  queue_head_s <= unpack_meta(queue_s(head_s));
  queue_next_s <= unpack_meta(queue_s(next_q(head_s)));
  activity_baseline_s <= raw_baseline(current_s.baseline,current_s.positive_pulse);
  publish_drop_s <= '1' when desc_busy_i='0' and queue_count_s>0 and
    seq_age(seq_s,queue_head_s.start_seq)>RETENTION_LIMIT_C else '0';
  consume_drop_s <= '1' when published_count_s>0 and dropped_s(to_integer(read_slot_s))='1' else '0';
  drop_bitmap_proc : process(clock_i)
  begin
    if rising_edge(clock_i) then
      if reset_i='1' then dropped_s<=(others=>'0');
      else
        for i in 0 to PACKET_SLOT_COUNT_C-1 loop
          if consume_drop_s='1' and read_slot_s=to_unsigned(i,read_slot_s'length) then dropped_s(i)<='0'; end if;
          if publish_drop_s='1' and queue_head_s.slot=to_unsigned(i,queue_head_s.slot'length) then dropped_s(i)<='1'; end if;
        end loop;
      end if;
    end if;
  end process;
  selected_trigger_pulse_s <= trigger_i.trigger_pulse and timing_trigger_enable_i
    when trigger_i.calibration_tag = CALIBRATION_TAG_TIMING_C else
    trigger_i.trigger_pulse and self_trigger_enable_i;
  event_pulse_s <= selected_trigger_pulse_s or force_trigger_i;
  event_sample_s <= din_i when force_trigger_i='1' else trigger_i.trigger_sample;
  event_tag_s <= force_calibration_tag_i when force_trigger_i='1' else trigger_i.calibration_tag;
  -- Kept for legacy diagnostic calculator compatibility; packet descriptors use
  -- explicit fragment-local start/sample-valid handshakes below.
  frame_match_o <= '1' when enable_i='1' and queue_count_s<FRAME_QUEUE_DEPTH_C and
                   reserved_count_s<PACKET_SLOT_COUNT_C else '0';
  delayed_sample_o <= din_i;
  -- All reserved slots include pending captures, serialization and output words.
  drained_o <= '1' when reset_i='0' and enable_i='0' and chain_active_s='0' and
    reserved_count_s=0 and queue_count_s=0 and desc_busy_i='0' else '0';
  ready_o <= '1' when published_count_s>0 and dropped_s(to_integer(read_slot_s))='0' else '0';

  desc_o <= ch_id_i & version_i & pack_meta(queue_head_s);
  desc_valid_o <= '1' when queue_count_s>0 and
    seq_age(seq_s,queue_head_s.start_seq)>=FRAME_SAMPLE_COUNT_C-1 and
    seq_age(seq_s,queue_head_s.start_seq)<=RETENTION_LIMIT_C else '0';
  ring_inst : entity work.grouped_sample_ring
    port map(clock_i=>clock_i, builder_clock_i=>builder_clock_i,
      wr_en_i=>not reset_i, wr_addr_i=>seq_s(10 downto 0), din_i=>din_i,
      rd_addr_i=>ring_rd_addr_i, dout_o=>ring_data_o);
  store_inst : entity work.packet_frame_store
    port map(clock_i=>clock_i, wr_en_i=>packet_wr_i and not reset_i,
      wr_addr_i=>packet_addr_i, din_i=>packet_data_i,
      rd_addr_i=>store_raddr_s, dout_o=>dout_o);
  store_rd_addr_proc : process(all)
  begin
    store_raddr_s <= slot_addr(read_slot_s,read_word_s);
    if consume_drop_s='1' then
      store_raddr_s <= slot_addr(read_slot_s+1,0);
    elsif rd_en_i='1' and published_count_s>0 and dropped_s(to_integer(read_slot_s))='0' then
      if read_word_s=FRAME_WORD_COUNT_C-1 then store_raddr_s<=slot_addr(read_slot_s+1,0);
      else store_raddr_s<=slot_addr(read_slot_s,read_word_s+1); end if;
    end if;
  end process;
  main_proc : process(clock_i)
    variable pending_head : frame_meta_t;
    variable head, tail, count : natural range 0 to FRAME_QUEUE_DEPTH_C;
    variable reserved, published : natural range 0 to PACKET_SLOT_COUNT_C;
    variable req : frame_meta_t;
    variable req_valid, req_cont, req_first, accepted, covered : boolean;
    variable event_end_seq, candidate_start_seq : sample_seq_t;
    variable age : natural range 0 to RING_DEPTH_C+1;
    variable workload : natural range 0 to 5*SERIALIZER_CYCLES_C;
    variable wait_cycles : natural range 0 to 511;
    variable quiet_next, quiet_limit : natural range 0 to 511;
    variable min_spacing : natural range 1 to 512;
    variable residual : integer range -16383 to 16383;
    variable activity_next : std_logic;
  begin
    if rising_edge(clock_i) then
      if reset_i='1' then
        seq_s<=(others=>'0'); history_s<=0; head_s<=0; tail_s<=0; queue_count_s<=0;
        timestamp_previous_s<=(others=>'0'); timestamp_armed_s<='0';
        allocate_slot_s<=(others=>'0'); read_slot_s<=(others=>'0');
        reserved_count_s<=0; published_count_s<=0; read_word_s<=0;
        chain_active_s<='0'; current_accepted_s<='0'; previous_accepted_s<='0';
        current_s<=META_NULL_C; previous_s<=META_NULL_C; older_start_s<=(others=>'0'); older_accepted_s<='0'; activity_s<='0'; quiet_s<=0; chain_quiet_limit_s<=32;
        required_end_s<=(others=>'0'); last_start_s<=(others=>'0'); last_start_valid_s<='0'; trigger_previous_s<='0';
        record_count_s<=(others=>'0'); full_count_s<=(others=>'0'); busy_count_s<=(others=>'0');
        spacing_count_s<=(others=>'0'); queue_drop_s<=(others=>'0'); ring_drop_s<=(others=>'0');
        trigger_count_s<=(others=>'0'); packet_count_s<=(others=>'0'); continuation_count_s<=(others=>'0');
        continuation_drop_s<=(others=>'0'); covered_count_s<=(others=>'0'); descriptor_overflow_count_s<=(others=>'0');
      else
        pending_head:=queue_head_s; head:=head_s; tail:=tail_s; count:=queue_count_s;
        reserved:=reserved_count_s; published:=published_count_s;
        seq_s<=seq_s+1;
        timestamp_previous_s<=unsigned(timestamp_i); timestamp_armed_s<='1';
        -- Expire the spacing reference before the local modulo sample counter
        -- can wrap and make an ancient fragment appear recent again.
        if last_start_valid_s='1' and seq_age(seq_s,last_start_s)>RING_DEPTH_C then
          last_start_valid_s<='0';
        end if;
        if current_accepted_s='1' and seq_age(seq_s,current_s.start_seq)>RING_DEPTH_C then
          current_accepted_s<='0';
        end if;
        if older_accepted_s='1' and seq_age(seq_s,older_start_s)>RING_DEPTH_C then
          older_accepted_s<='0';
        end if;
        if previous_accepted_s='1' and seq_age(seq_s,previous_s.start_seq)>RING_DEPTH_C then
          previous_accepted_s<='0';
        end if;
        if history_s<RING_DEPTH_C then history_s<=history_s+1; end if;
        if timestamp_jump_s='1' then
          -- Start a new admission epoch; reserved packet ownership and the
          -- uninterrupted raw-sample ring/serializer keep draining unchanged.
          history_s<=0; current_accepted_s<='0'; previous_accepted_s<='0'; older_accepted_s<='0'; last_start_valid_s<='0';
        end if;
        trigger_previous_s<=selected_trigger_pulse_s;
        if selected_trigger_pulse_s='1' and trigger_previous_s='0' and enable_i='1' then
          trigger_count_s<=trigger_count_s+1;
        end if;
        -- Releasing or skipping a slot is the sole operation returning a credit.
        if consume_drop_s='1' then
          read_slot_s<=read_slot_s+1; read_word_s<=0; reserved:=reserved-1; published:=published-1;
        elsif rd_en_i='1' and published_count_s>0 and dropped_s(to_integer(read_slot_s))='0' then
          if read_word_s=FRAME_WORD_COUNT_C-1 then
            read_slot_s<=read_slot_s+1; read_word_s<=0;
            reserved:=reserved-1; published:=published-1;
          else read_word_s<=read_word_s+1; end if;
        end if;
        if packet_commit_i='1' then
          assert packet_wr_i='1' and queue_count_s>0 and desc_busy_i='1'
            report "grouped commit without an owned descriptor" severity failure;
          assert packet_addr_i=slot_addr(queue_head_s.slot,6)
            report "grouped packet committed into the wrong reserved slot" severity failure;
          published:=published+1; record_count_s<=record_count_s+1;
          if packet_overflow_i='1' then descriptor_overflow_count_s<=descriptor_overflow_count_s+1; end if;
          head:=next_q(head); count:=count-1; pending_head:=queue_next_s;
        elsif publish_drop_s='1' then
          published:=published+1;
          ring_drop_s<=ring_drop_s+1; busy_count_s<=busy_count_s+1;
          if pending_head.continuation='1' then continuation_drop_s<=continuation_drop_s+1; end if;
          head:=next_q(head); count:=count-1; pending_head:=queue_next_s;
        end if;

        req:=META_NULL_C; req_valid:=false; req_cont:=false; req_first:=false;
        quiet_next:=quiet_s; activity_next:=activity_s;
        -- Evaluate the inclusive final sample before deciding the next fragment.
        if chain_active_s='1' and enable_i='1' and continuation_enable_i='1' and timestamp_jump_s='0' then
          if current_s.positive_pulse='1' then residual:=to_integer(unsigned(din_i))-to_integer(unsigned(activity_baseline_s));
          else residual:=to_integer(unsigned(activity_baseline_s))-to_integer(unsigned(din_i)); end if;
          if activity_s='0' and residual>=to_integer(unsigned(current_s.activity_threshold)) then activity_next:='1';
          elsif activity_s='1' and residual<=to_integer(unsigned(current_s.activity_threshold))/2 then activity_next:='0'; end if;
          if activity_next='1' then quiet_next:=0;
          elsif quiet_next<chain_quiet_limit_s then quiet_next:=quiet_next+1; end if;
          activity_s<=activity_next; quiet_s<=quiet_next;
          if seq_s-current_s.start_seq>=FRAME_SAMPLE_COUNT_C-1 then
            -- A satisfied deadline may otherwise age through the signed
            -- half-range during a long tail. Advancing it to the frame end
            -- preserves whether more posttrigger samples are still required.
            if signed(required_end_s-(current_s.start_seq+FRAME_SAMPLE_COUNT_C-1))<=0 then
              required_end_s<=current_s.start_seq+FRAME_SAMPLE_COUNT_C-1;
            end if;
            if quiet_next<chain_quiet_limit_s or signed(required_end_s-(current_s.start_seq+FRAME_SAMPLE_COUNT_C-1))>0 then
              req:=current_s; req.start_seq:=current_s.start_seq+FRAME_SAMPLE_COUNT_C;
              req.sample0_ts:=std_logic_vector(unsigned(current_s.sample0_ts)+FRAME_SAMPLE_COUNT_C);
              req.continuation:='1'; req.trigger_sample:=din_i;
              req_valid:=true; req_cont:=true;
              older_start_s<=previous_s.start_seq; older_accepted_s<=previous_accepted_s;
              previous_s<=current_s; previous_accepted_s<=current_accepted_s;
              current_s<=req; current_accepted_s<='0';
            else chain_active_s<='0'; end if;
          end if;
        elsif enable_i='0' or continuation_enable_i='0' or timestamp_jump_s='1' then
          chain_active_s<='0'; activity_s<='0'; quiet_s<=0;
        end if;

        if event_pulse_s='1' and enable_i='1' then
          -- Supported tuples arrive at most447 clocks after the trigger;
          -- jump-edge/older/future tuples are whole losses before local matching.
          if timestamp_jump_s='1' or event_age_s>POSTTRIGGER_SAMPLES_C then
            ring_drop_s<=ring_drop_s+1; busy_count_s<=busy_count_s+1;
          else
            covered := (current_accepted_s='1' and seq_age(seq_s,current_s.start_seq)<=RING_DEPTH_C and
                        inside_window(current_delta_s,continuation_enable_i)) or
                       (previous_accepted_s='1' and seq_age(seq_s,previous_s.start_seq)<=RING_DEPTH_C and
                        inside_window(previous_delta_s,continuation_enable_i)) or
                       (older_accepted_s='1' and seq_age(seq_s,older_start_s)<=RING_DEPTH_C and
                        inside_window(older_delta_s,continuation_enable_i));
            if covered then
              covered_count_s<=covered_count_s+1;
              -- A coalesced trigger still owns its complete trigger..trigger+447
              -- posttrigger interval. Delayed trigger delivery may reopen the
              -- last quiet-closed chain from retained samples, without shifting
              -- its 256-sample grid or adding another pretrigger region.
              if continuation_enable_i='1' then
                event_end_seq:=event_seq_s+POSTTRIGGER_SAMPLES_C;
                if signed(event_end_seq-required_end_s)>0 then required_end_s<=event_end_seq; end if;
                if signed(event_end_seq-(current_s.start_seq+FRAME_SAMPLE_COUNT_C-1))>0 and
                   seq_s-current_s.start_seq>=FRAME_SAMPLE_COUNT_C-1 and not req_valid then
                  req:=current_s; req.start_seq:=current_s.start_seq+FRAME_SAMPLE_COUNT_C;
                  req.sample0_ts:=std_logic_vector(unsigned(current_s.sample0_ts)+FRAME_SAMPLE_COUNT_C);
                  req.continuation:='1'; req.trigger_sample:=event_sample_s;
                  req_valid:=true; req_cont:=true;
                  older_start_s<=previous_s.start_seq; older_accepted_s<=previous_accepted_s;
              previous_s<=current_s; previous_accepted_s<=current_accepted_s;
                  current_s<=req; current_accepted_s<='0'; chain_active_s<='1';
                end if;
              end if;
            elsif chain_active_s='1' or req_valid then
              -- A trigger in a denied fragment does not shift the chain grid.
              busy_count_s<=busy_count_s+1;
            else
              age:=to_integer(event_age_s(8 downto 0))+PRETRIGGER_SAMPLES_C;
              min_spacing:=FRAME_SAMPLE_COUNT_C;
              if continuation_enable_i='0' then
                if to_integer(unsigned(signal_delay_i))*16>=FRAME_SAMPLE_COUNT_C then min_spacing:=16;
                else min_spacing:=FRAME_SAMPLE_COUNT_C-to_integer(unsigned(signal_delay_i))*16; end if;
              end if;
              candidate_start_seq:=seq_s-to_unsigned(age,sample_seq_t'length);
              if age>history_s then
                ring_drop_s<=ring_drop_s+1; busy_count_s<=busy_count_s+1;
              elsif last_start_valid_s='1' and seq_age(seq_s,last_start_s)<=RING_DEPTH_C and
                    signed(candidate_start_seq-last_start_s)<to_signed(min_spacing,sample_seq_t'length) then
                spacing_count_s<=spacing_count_s+1; busy_count_s<=busy_count_s+1;
              else
                req:=META_NULL_C; req.start_seq:=seq_s-to_unsigned(age,sample_seq_t'length);
                req.sample0_ts:=event_sample0_ts_s;
                req.baseline:=trigger_i.baseline;
                req.trigger_sample:=event_sample_s; req.threshold_lsb:=threshold_xc_i(13 downto 0);
                req.activity_threshold:=activity_threshold_i;
                if unsigned(activity_threshold_i)=0 then req.activity_threshold:=std_logic_vector(to_unsigned(1,14)); end if;
                req.positive_pulse:=positive_pulse_i; req.calibration_tag:=event_tag_s;
                req_valid:=true; req_first:=true;
              end if;
            end if;
          end if;
        end if;
        if req_valid then
          age:=seq_age(seq_s,req.start_seq);
          -- Conservative four-channel service bound in ADC clocks. The head
          -- stays counted through final-header commit. Multiplication by 512
          -- is a shift; the 64-sample retention margin covers CDC latency.
          workload:=count*SERIALIZER_CYCLES_C;
          wait_cycles:=0;
          if count>0 and seq_age(seq_s,pending_head.start_seq)<FRAME_SAMPLE_COUNT_C-1 then
            wait_cycles:=FRAME_SAMPLE_COUNT_C-1-seq_age(seq_s,pending_head.start_seq);
          end if;
          accepted:=false;
          if reserved=PACKET_SLOT_COUNT_C then full_count_s<=full_count_s+1;
          elsif count=FRAME_QUEUE_DEPTH_C then queue_drop_s<=queue_drop_s+1; busy_count_s<=busy_count_s+1;
          elsif age+workload+wait_cycles>RETENTION_LIMIT_C then ring_drop_s<=ring_drop_s+1; busy_count_s<=busy_count_s+1;
          else
            req.slot:=allocate_slot_s;
            allocate_slot_s<=allocate_slot_s+1; reserved:=reserved+1;
            queue_s(tail_s)<=pack_meta(req); tail:=next_q(tail); count:=count+1; accepted:=true;
            packet_count_s<=packet_count_s+1; last_start_s<=req.start_seq; last_start_valid_s<='1';
            if req_cont then continuation_count_s<=continuation_count_s+1; end if;
          end if;
          if req_cont then
            if accepted then current_s<=req; current_accepted_s<='1';
            else continuation_drop_s<=continuation_drop_s+1; end if;
          elsif req_first and accepted then
            older_start_s<=previous_s.start_seq; older_accepted_s<=previous_accepted_s;
              previous_s<=current_s; previous_accepted_s<=current_accepted_s;
            current_s<=req; current_accepted_s<='1';
            chain_active_s<=continuation_enable_i; activity_s<='0'; quiet_s<=0;
            required_end_s<=req.start_seq+PRETRIGGER_SAMPLES_C+POSTTRIGGER_SAMPLES_C;
            quiet_limit:=to_integer(unsigned(quiet_samples_i));
            if quiet_limit=0 then quiet_limit:=1; end if;
            chain_quiet_limit_s<=quiet_limit;
          end if;
        end if;
        if enable_i='0' then
          -- End the admission epoch, retaining queued packet ownership. New
          -- sources must not coalesce into metadata from the previous mode.
          current_accepted_s<='0'; previous_accepted_s<='0'; older_accepted_s<='0'; last_start_valid_s<='0';
        end if;
        -- Counter reset is deliberately independent of acquisition state: it
        -- cannot leave a partial packet in the transport stream.
        if reset_st_counters_i='1' then
          record_count_s<=(others=>'0'); full_count_s<=(others=>'0'); busy_count_s<=(others=>'0');
          spacing_count_s<=(others=>'0'); queue_drop_s<=(others=>'0'); ring_drop_s<=(others=>'0');
          trigger_count_s<=(others=>'0'); packet_count_s<=(others=>'0'); continuation_count_s<=(others=>'0');
          continuation_drop_s<=(others=>'0'); covered_count_s<=(others=>'0'); descriptor_overflow_count_s<=(others=>'0');
        end if;
        -- synthesis translate_off
        assert reserved=published+count report "grouped reservation conservation failed" severity failure;
        -- synthesis translate_on
        head_s<=head; tail_s<=tail; queue_count_s<=count;
        reserved_count_s<=reserved; published_count_s<=published;
      end if;
    end if;
  end process;
  record_count_o<=std_logic_vector(resize(record_count_s,64));
  full_count_o<=std_logic_vector(resize(full_count_s,64));
  busy_count_o<=std_logic_vector(resize(busy_count_s,64));
  spacing_reject_count_o<=std_logic_vector(resize(spacing_count_s,64));
  queue_reject_count_o<=std_logic_vector(resize(queue_drop_s,64));
  ring_reject_count_o<=std_logic_vector(resize(ring_drop_s,64));
  output_reject_count_o<=std_logic_vector(resize(full_count_s,64));
  trigger_count_o<=std_logic_vector(resize(trigger_count_s,64));
  packet_count_o<=std_logic_vector(resize(packet_count_s,64));
  continuation_count_o<=std_logic_vector(resize(continuation_count_s,64));
  continuation_drop_count_o<=std_logic_vector(resize(continuation_drop_s,64));
  covered_trigger_count_o<=std_logic_vector(resize(covered_count_s,64));
  descriptor_overflow_count_o<=std_logic_vector(resize(descriptor_overflow_count_s,64));
end architecture;
