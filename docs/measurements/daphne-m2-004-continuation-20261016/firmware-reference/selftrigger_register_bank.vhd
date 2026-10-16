library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library xpm;
use xpm.vcomponents.all;

use work.daphne_package.all;
use work.daphne_subsystem_pkg.all;

entity selftrigger_register_bank is
  generic (
    CHANNEL_COUNT_G : positive := 40;
    COUNTER_READ_TIMEOUT_G : positive := 1024
  );
  port (
    AXI_IN         : in  AXILITE_INREC;
    AXI_OUT        : out AXILITE_OUTREC;
    counter_clock_i : in std_logic;
    pause_mask_o : out std_logic_vector(31 downto 0);
    pause_applied_i, drained_i : in std_logic_vector(31 downto 0) := (others=>'0');
    calibration_mask_o : out std_logic_vector(31 downto 0);
    calibration_applied_i : in std_logic_vector(31 downto 0) := (others=>'0');
    threshold_xc_o : out slv28_array_t(0 to CHANNEL_COUNT_G - 1);
    continuation_config_o : out slv32_array_t(0 to CHANNEL_COUNT_G - 1);
    record_count_i : in  slv64_array_t(0 to CHANNEL_COUNT_G - 1);
    full_count_i   : in  slv64_array_t(0 to CHANNEL_COUNT_G - 1);
    busy_count_i   : in  slv64_array_t(0 to CHANNEL_COUNT_G - 1);
    tcount_i       : in  slv64_array_t(0 to CHANNEL_COUNT_G - 1);
    pcount_i       : in  slv64_array_t(0 to CHANNEL_COUNT_G - 1);
    continuation_count_i : in slv64_array_t(0 to CHANNEL_COUNT_G - 1) := (others => (others => '0'));
    continuation_drop_count_i : in slv64_array_t(0 to CHANNEL_COUNT_G - 1) := (others => (others => '0'));
    covered_trigger_count_i : in slv64_array_t(0 to CHANNEL_COUNT_G - 1) := (others => (others => '0'));
    descriptor_overflow_count_i : in slv64_array_t(0 to CHANNEL_COUNT_G - 1) := (others => (others => '0'))
  );
end entity selftrigger_register_bank;

architecture rtl of selftrigger_register_bank is
  constant CALIBRATION_MASK_C : integer := 16#F00#;
  constant CALIBRATION_APPLIED_C : integer := 16#F04#;
  constant CALIBRATION_CAPABILITY_C : integer := 16#F08#;
  signal calibration_mask_reg, pause_mask_reg : std_logic_vector(31 downto 0) := (others=>'0');
  signal requested_masks, sample_masks : std_logic_vector(63 downto 0);
  signal applied_masks, axi_status : std_logic_vector(95 downto 0) := (others=>'0');
  signal calibration_valid, calibration_applied_valid : std_logic;
  constant CHANNEL_STRIDE_C        : integer := 16#20#;
  constant THRESHOLD_OFFSET_C      : integer := 16#00#;
  constant RECORD_COUNT_LO_C       : integer := 16#04#;
  constant RECORD_COUNT_HI_C       : integer := 16#08#;
  constant BUSY_COUNT_LO_C         : integer := 16#0C#;
  constant BUSY_COUNT_HI_C         : integer := 16#10#;
  constant FULL_COUNT_LO_C         : integer := 16#14#;
  constant FULL_COUNT_HI_C         : integer := 16#18#;
  constant CONTINUATION_CONFIG_C   : integer := 16#1C#;
  constant PRIMITIVE_BASE_C        : integer := 16#500#;
  constant PRIMITIVE_STRIDE_C      : integer := 16#10#;
  constant TCOUNT_LO_OFFSET_C      : integer := 16#00#;
  constant TCOUNT_HI_OFFSET_C      : integer := 16#04#;
  constant PCOUNT_LO_OFFSET_C      : integer := 16#08#;
  constant PCOUNT_HI_OFFSET_C      : integer := 16#0C#;

  signal threshold_xc_reg : slv28_array_t(0 to CHANNEL_COUNT_G - 1) := (others => (others => '1'));
  signal continuation_config_reg : slv32_array_t(0 to CHANNEL_COUNT_G - 1) := (others => CONTINUATION_CONFIG_DEFAULT_C);

  signal axi_awaddr   : std_logic_vector(31 downto 0) := (others => '0');
  signal axi_awready  : std_logic := '0';
  signal axi_wready   : std_logic := '0';
  signal axi_bresp    : std_logic_vector(1 downto 0) := "00";
  signal axi_bvalid   : std_logic := '0';
  signal axi_arready  : std_logic := '0';
  signal axi_rdata    : std_logic_vector(31 downto 0) := (others => '0');
  signal axi_rresp    : std_logic_vector(1 downto 0) := "00";
  signal axi_rvalid   : std_logic := '0';
  signal reg_wren     : std_logic;
  signal aw_en        : std_logic := '1';

  -- Decode in AXI, then send only the counter selector to the acquisition
  -- domain. A held 64-bit snapshot returns through a separate handshake.
  type read_decode_t is record
    counter : integer range -1 to CHANNEL_COUNT_G * 9 - 1;
    channel : natural range 0 to CHANNEL_COUNT_G - 1;
    high_word, local_valid, continuation : boolean;
  end record;
  function decode_read(addr : natural) return read_decode_t is
    variable d : read_decode_t := (-1, 0, false, false, false);
    variable offset : natural;
  begin
    for channel in 0 to CHANNEL_COUNT_G - 1 loop
      if addr >= channel * CHANNEL_STRIDE_C and addr < (channel + 1) * CHANNEL_STRIDE_C then
        d.channel := channel;
        offset := addr - channel * CHANNEL_STRIDE_C;
        case offset is
          when THRESHOLD_OFFSET_C => d.local_valid := true;
          when CONTINUATION_CONFIG_C => d.local_valid := true; d.continuation := true;
          when RECORD_COUNT_LO_C | RECORD_COUNT_HI_C =>
            d.counter := channel * 9; d.high_word := offset = RECORD_COUNT_HI_C;
          when BUSY_COUNT_LO_C | BUSY_COUNT_HI_C =>
            d.counter := channel * 9 + 1; d.high_word := offset = BUSY_COUNT_HI_C;
          when FULL_COUNT_LO_C | FULL_COUNT_HI_C =>
            d.counter := channel * 9 + 2; d.high_word := offset = FULL_COUNT_HI_C;
          when others => null;
        end case;
      elsif addr >= PRIMITIVE_BASE_C + channel * PRIMITIVE_STRIDE_C and
            addr < PRIMITIVE_BASE_C + (channel + 1) * PRIMITIVE_STRIDE_C then
        offset := addr - PRIMITIVE_BASE_C - channel * PRIMITIVE_STRIDE_C;
        case offset is
          when 0 | 4 => d.counter := channel * 9 + 3; d.high_word := offset = 4;
          when 8 | 12 => d.counter := channel * 9 + 4; d.high_word := offset = 12;
          when others => null;
        end case;
      elsif addr >= 16#800# + channel * 32 and addr < 16#800# + (channel + 1) * 32 then
        offset := addr - 16#800# - channel * 32;
        if offset mod 4 = 0 then
          d.counter := channel * 9 + 5 + offset / 8;
          d.high_word := offset mod 8 = 4;
        end if;
      end if;
    end loop;
    return d;
  end function;

  type read_state_t is (READ_IDLE, READ_LAUNCH, READ_WAIT_DATA, READ_RESPONSE);
  signal read_state : read_state_t := READ_IDLE;
  signal read_high : boolean := false;
  signal read_counter, cached_counter : natural range 0 to CHANNEL_COUNT_G * 9 - 1 := 0;
  signal cached_value : std_logic_vector(63 downto 0) := (others => '0');
  signal cached_valid : boolean := false;
  signal read_timeout : natural range 0 to COUNTER_READ_TIMEOUT_G - 1 := 0;
  signal launch : std_logic := '0';
  signal launch_selector : std_logic_vector(8 downto 0) := (others => '0');

  type request_state_t is (REQUEST_IDLE, REQUEST_WAIT_ACK, REQUEST_RESPONSE, REQUEST_DRAIN);
  signal request_state : request_state_t := REQUEST_IDLE;
  signal request_hold, request_value : std_logic_vector(8 downto 0) := (others => '0');
  signal request_send, request_received, request_valid, request_ack : std_logic := '0';
  signal response_hold, response_value, response_data : std_logic_vector(63 downto 0) := (others => '0');
  signal response_send, response_received, response_request, response_ack, response_valid : std_logic := '0';
  signal response_seen : boolean := false;
  type snapshot_state_t is (SNAPSHOT_IDLE, SNAPSHOT_SEND, SNAPSHOT_DRAIN);
  signal snapshot_state : snapshot_state_t := SNAPSHOT_IDLE;
begin
  assert CHANNEL_COUNT_G <= 40 report "Counter address map supports at most 40 channels" severity failure;
  calibration_to_sample : entity work.pdts_cdc_snapshot
    generic map(WIDTH_G=>64)
    port map(src_clk_i=>AXI_IN.ACLK, src_data_i=>requested_masks,
      dst_clk_i=>counter_clock_i, dst_reset_i=>not AXI_IN.ARESETN,
      dst_data_o=>sample_masks, dst_valid_o=>calibration_valid, dst_update_o=>open);
  calibration_to_axi : entity work.pdts_cdc_snapshot
    generic map(WIDTH_G=>96)
    port map(src_clk_i=>counter_clock_i, src_data_i=>applied_masks,
      dst_clk_i=>AXI_IN.ACLK, dst_reset_i=>not AXI_IN.ARESETN,
      dst_data_o=>axi_status, dst_valid_o=>calibration_applied_valid, dst_update_o=>open);
  requested_masks <= pause_mask_reg & calibration_mask_reg;
  applied_masks <= drained_i & pause_applied_i & calibration_applied_i;
  calibration_mask_o <= sample_masks(31 downto 0) when calibration_valid='1' else (others=>'0');
  pause_mask_o <= sample_masks(63 downto 32) when calibration_valid='1' else (others=>'0');
  threshold_xc_o <= threshold_xc_reg;
  continuation_config_o <= continuation_config_reg;

  AXI_OUT.AWREADY <= axi_awready;
  AXI_OUT.WREADY  <= axi_wready;
  AXI_OUT.BRESP   <= axi_bresp;
  AXI_OUT.BVALID  <= axi_bvalid;
  AXI_OUT.ARREADY <= axi_arready;
  AXI_OUT.RDATA   <= axi_rdata;
  AXI_OUT.RRESP   <= axi_rresp;
  AXI_OUT.RVALID  <= axi_rvalid;

  process (AXI_IN.ACLK)
  begin
    if rising_edge(AXI_IN.ACLK) then
      if AXI_IN.ARESETN = '0' then
        axi_awready <= '0';
        aw_en <= '1';
      else
        if axi_awready = '0' and AXI_IN.AWVALID = '1' and AXI_IN.WVALID = '1' and aw_en = '1' then
          axi_awready <= '1';
          aw_en <= '0';
        elsif AXI_IN.BREADY = '1' and axi_bvalid = '1' then
          aw_en <= '1';
          axi_awready <= '0';
        else
          axi_awready <= '0';
        end if;
      end if;
    end if;
  end process;

  process (AXI_IN.ACLK)
  begin
    if rising_edge(AXI_IN.ACLK) then
      if AXI_IN.ARESETN = '0' then
        axi_awaddr <= (others => '0');
      else
        if axi_awready = '0' and AXI_IN.AWVALID = '1' and AXI_IN.WVALID = '1' and aw_en = '1' then
          axi_awaddr <= AXI_IN.AWADDR;
        end if;
      end if;
    end if;
  end process;

  process (AXI_IN.ACLK)
  begin
    if rising_edge(AXI_IN.ACLK) then
      if AXI_IN.ARESETN = '0' then
        axi_wready <= '0';
      else
        if axi_wready = '0' and AXI_IN.WVALID = '1' and AXI_IN.AWVALID = '1' and aw_en = '1' then
          axi_wready <= '1';
        else
          axi_wready <= '0';
        end if;
      end if;
    end if;
  end process;

  reg_wren <= axi_wready and AXI_IN.WVALID and axi_awready and AXI_IN.AWVALID;

  process (AXI_IN.ACLK)
    variable addr_v : integer;
  begin
    if rising_edge(AXI_IN.ACLK) then
      if AXI_IN.ARESETN = '0' then
        calibration_mask_reg <= (others=>'0'); pause_mask_reg <= (others=>'0');
        for idx in 0 to CHANNEL_COUNT_G - 1 loop
          threshold_xc_reg(idx) <= (others => '1');
          continuation_config_reg(idx) <= CONTINUATION_CONFIG_DEFAULT_C;
        end loop;
      else
        if reg_wren = '1' and AXI_IN.WSTRB = "1111" then
          addr_v := to_integer(unsigned(axi_awaddr(11 downto 0)));
          if addr_v = 16#F0C# then pause_mask_reg <= AXI_IN.WDATA; end if;
          if addr_v = CALIBRATION_MASK_C then calibration_mask_reg <= AXI_IN.WDATA; end if;
          for idx in 0 to CHANNEL_COUNT_G - 1 loop
            if addr_v = idx * CHANNEL_STRIDE_C + THRESHOLD_OFFSET_C then
              threshold_xc_reg(idx) <= AXI_IN.WDATA(27 downto 0);
            elsif addr_v = idx * CHANNEL_STRIDE_C + CONTINUATION_CONFIG_C then
              continuation_config_reg(idx) <= AXI_IN.WDATA and x"81FF3FFF";
            end if;
          end loop;
        end if;
      end if;
    end if;
  end process;

  process (AXI_IN.ACLK)
  begin
    if rising_edge(AXI_IN.ACLK) then
      if AXI_IN.ARESETN = '0' then
        axi_bvalid <= '0';
        axi_bresp <= "00";
      else
        if axi_awready = '1' and AXI_IN.AWVALID = '1' and axi_wready = '1' and AXI_IN.WVALID = '1' and axi_bvalid = '0' then
          axi_bvalid <= '1';
          axi_bresp <= "00";
        elsif AXI_IN.BREADY = '1' and axi_bvalid = '1' then
          axi_bvalid <= '0';
        end if;
      end if;
    end if;
  end process;

  -- One outstanding AXI read; ARREADY cannot acknowledge another address
  -- while a counter request or a backpressured response is pending.
  axi_arready <= '1' when read_state = READ_IDLE and AXI_IN.ARESETN = '1' else '0';
  process(AXI_IN.ACLK)
    variable decoded : read_decode_t;
  begin
    if rising_edge(AXI_IN.ACLK) then
      launch <= '0';
      if AXI_IN.ARESETN = '0' then
        read_state <= READ_IDLE;
        axi_rvalid <= '0'; axi_rresp <= "00"; axi_rdata <= (others => '0');
        cached_valid <= false;
      else
        case read_state is
          when READ_IDLE =>
            if AXI_IN.ARVALID = '1' then
              decoded := decode_read(to_integer(unsigned(AXI_IN.ARADDR(11 downto 0))));
              axi_rresp <= "00";
              axi_rdata <= (others => '0');
              if to_integer(unsigned(AXI_IN.ARADDR(11 downto 0))) = CALIBRATION_MASK_C then
                axi_rdata <= calibration_mask_reg; axi_rvalid <= '1'; read_state <= READ_RESPONSE;
              elsif to_integer(unsigned(AXI_IN.ARADDR(11 downto 0))) = CALIBRATION_APPLIED_C then
                if calibration_applied_valid='1' then axi_rdata <= axi_status(31 downto 0); end if;
                axi_rvalid <= '1'; read_state <= READ_RESPONSE;
              elsif to_integer(unsigned(AXI_IN.ARADDR(11 downto 0))) = CALIBRATION_CAPABILITY_C then
                axi_rdata <= x"43414C32"; axi_rvalid <= '1'; read_state <= READ_RESPONSE;
              elsif to_integer(unsigned(AXI_IN.ARADDR(11 downto 0))) = 16#F0C# then
                axi_rdata <= pause_mask_reg; axi_rvalid <= '1'; read_state <= READ_RESPONSE;
              elsif to_integer(unsigned(AXI_IN.ARADDR(11 downto 0))) = 16#F10# then
                if calibration_applied_valid='1' then axi_rdata <= axi_status(63 downto 32); end if;
                axi_rvalid <= '1'; read_state <= READ_RESPONSE;
              elsif to_integer(unsigned(AXI_IN.ARADDR(11 downto 0))) = 16#F14# then
                if calibration_applied_valid='1' then axi_rdata <= axi_status(95 downto 64); end if;
                axi_rvalid <= '1'; read_state <= READ_RESPONSE;
              elsif decoded.counter = -1 then
                if decoded.local_valid then
                  if decoded.continuation then
                    axi_rdata <= continuation_config_reg(decoded.channel);
                  else
                    axi_rdata <= "0000" & threshold_xc_reg(decoded.channel);
                  end if;
                end if;
                axi_rvalid <= '1'; read_state <= READ_RESPONSE;
              elsif decoded.high_word and cached_valid and decoded.counter = cached_counter then
                -- An immediately paired high word uses the same 64-bit epoch
                -- as its low word, including carry across bit 31.
                axi_rdata <= cached_value(63 downto 32);
                cached_valid <= false;
                axi_rvalid <= '1'; read_state <= READ_RESPONSE;
              else
                launch_selector <= std_logic_vector(to_unsigned(decoded.counter, 9));
                read_counter <= decoded.counter; read_high <= decoded.high_word;
                cached_valid <= false; read_timeout <= 0;
                read_state <= READ_LAUNCH;
              end if;
            end if;
          when READ_LAUNCH =>
            -- Normal reads can arrive before the previous exchange finishes
            -- its return-to-zero phase. Wait for it, including an orphaned
            -- transfer after timeout/reset, without accepting its old data.
            if request_state = REQUEST_IDLE and launch = '0' then
              launch <= '1'; read_state <= READ_WAIT_DATA;
            elsif read_timeout = COUNTER_READ_TIMEOUT_G - 1 then
              axi_rresp <= "10"; axi_rvalid <= '1'; read_state <= READ_RESPONSE;
            else
              read_timeout <= read_timeout + 1;
            end if;
          when READ_WAIT_DATA =>
            if response_valid = '1' then
              if read_high then axi_rdata <= response_data(63 downto 32);
              else axi_rdata <= response_data(31 downto 0); end if;
              cached_counter <= read_counter; cached_value <= response_data;
              cached_valid <= not read_high;
              axi_rvalid <= '1'; read_state <= READ_RESPONSE;
            elsif read_timeout = COUNTER_READ_TIMEOUT_G - 1 then
              -- The acquisition clock may stop. Complete AXI with SLVERR;
              -- the resetless XPM exchange continues until the clock returns.
              axi_rdata <= (others => '0'); axi_rresp <= "10";
              axi_rvalid <= '1'; read_state <= READ_RESPONSE;
            else
              read_timeout <= read_timeout + 1;
            end if;
          when READ_RESPONSE =>
            if AXI_IN.RREADY = '1' then
              axi_rvalid <= '0'; read_state <= READ_IDLE;
            end if;
        end case;
      end if;
    end if;
  end process;

  -- XPM handshakes have no reset. These protocol registers deliberately drain
  -- through AXI/acquisition resets; only the AXI client discards its old read.
  process(AXI_IN.ACLK)
  begin
    if rising_edge(AXI_IN.ACLK) then
      response_valid <= '0';
      response_ack <= response_request;
      if response_request = '1' and response_ack = '0' then
        response_data <= response_value;
        response_valid <= '1'; response_seen <= true;
      end if;
      case request_state is
        when REQUEST_IDLE =>
          if launch = '1' then
            request_hold <= launch_selector; request_send <= '1';
            response_seen <= false; request_state <= REQUEST_WAIT_ACK;
          end if;
        when REQUEST_WAIT_ACK =>
          if request_received = '1' then
            request_send <= '0'; request_state <= REQUEST_RESPONSE;
          end if;
        when REQUEST_RESPONSE =>
          if response_seen then request_state <= REQUEST_DRAIN; end if;
        when REQUEST_DRAIN =>
          if request_received = '0' and response_request = '0' and response_ack = '0' then
            request_state <= REQUEST_IDLE;
          end if;
      end case;
    end if;
  end process;

  counter_request : xpm_cdc_handshake
    generic map(DEST_EXT_HSK => 1, DEST_SYNC_FF => 3, INIT_SYNC_FF => 1,
      SIM_ASSERT_CHK => 1, SRC_SYNC_FF => 3, WIDTH => 9)
    port map(src_clk => AXI_IN.ACLK, src_in => request_hold, src_send => request_send,
      src_rcv => request_received, dest_clk => counter_clock_i, dest_out => request_value,
      dest_req => request_valid, dest_ack => request_ack);

  process(counter_clock_i)
    variable value : std_logic_vector(63 downto 0);
    variable selector : natural;
  begin
    if rising_edge(counter_clock_i) then
      case snapshot_state is
        when SNAPSHOT_IDLE =>
          if request_valid = '1' then
            selector := to_integer(unsigned(request_value));
            value := (others => '0');
            -- All selected counter bits are sampled together on their own
            -- clock. The mux no longer crosses directly into AXI registers.
            for channel in 0 to CHANNEL_COUNT_G - 1 loop
              if selector = channel * 9 then value := value or record_count_i(channel); end if;
              if selector = channel * 9 + 1 then value := value or busy_count_i(channel); end if;
              if selector = channel * 9 + 2 then value := value or full_count_i(channel); end if;
              if selector = channel * 9 + 3 then value := value or tcount_i(channel); end if;
              if selector = channel * 9 + 4 then value := value or pcount_i(channel); end if;
              if selector = channel * 9 + 5 then value := value or continuation_count_i(channel); end if;
              if selector = channel * 9 + 6 then value := value or continuation_drop_count_i(channel); end if;
              if selector = channel * 9 + 7 then value := value or covered_trigger_count_i(channel); end if;
              if selector = channel * 9 + 8 then value := value or descriptor_overflow_count_i(channel); end if;
            end loop;
            response_hold <= value; response_send <= '1'; request_ack <= '1';
            snapshot_state <= SNAPSHOT_SEND;
          end if;
        when SNAPSHOT_SEND =>
          if response_received = '1' then
            response_send <= '0'; snapshot_state <= SNAPSHOT_DRAIN;
          end if;
        when SNAPSHOT_DRAIN =>
          if response_received = '0' and request_valid = '0' then
            request_ack <= '0'; snapshot_state <= SNAPSHOT_IDLE;
          end if;
      end case;
    end if;
  end process;

  counter_response : xpm_cdc_handshake
    generic map(DEST_EXT_HSK => 1, DEST_SYNC_FF => 3, INIT_SYNC_FF => 1,
      SIM_ASSERT_CHK => 1, SRC_SYNC_FF => 3, WIDTH => 64)
    port map(src_clk => counter_clock_i, src_in => response_hold, src_send => response_send,
      src_rcv => response_received, dest_clk => AXI_IN.ACLK, dest_out => response_value,
      dest_req => response_request, dest_ack => response_ack);
end architecture rtl;
