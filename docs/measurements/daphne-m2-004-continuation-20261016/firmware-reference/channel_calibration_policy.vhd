library ieee;
use ieee.std_logic_1164.all;

-- Change admission only: filters, sample history and queued packets keep running.
entity channel_calibration_policy is
  generic (CHANNEL_COUNT_G : positive := 8; PIPELINE_CYCLES_G : positive := 64);
  port (
    clock_i, reset_i : in std_logic;
    calibration_mask_i : in std_logic_vector(CHANNEL_COUNT_G-1 downto 0);
    pause_mask_i : in std_logic_vector(CHANNEL_COUNT_G-1 downto 0) := (others=>'0');
    self_enable_i, timing_enable_i, force_trigger_i, inhibit_i : in std_logic;
    admission_o, self_enable_o, timing_enable_o, force_trigger_o : out std_logic_vector(CHANNEL_COUNT_G-1 downto 0);
    pause_applied_o : out std_logic_vector(CHANNEL_COUNT_G-1 downto 0);
    applied_mask_o : out std_logic_vector(CHANNEL_COUNT_G-1 downto 0)
  );
end entity;

architecture rtl of channel_calibration_policy is
  type holdoff_array_t is array(natural range <>) of natural range 0 to PIPELINE_CYCLES_G;
  signal holdoff : holdoff_array_t(0 to CHANNEL_COUNT_G-1) := (others=>0);
  signal previous_mask, applied_mask : std_logic_vector(CHANNEL_COUNT_G-1 downto 0) := (others=>'0');
  signal previous_pause, applied_pause : std_logic_vector(CHANNEL_COUNT_G-1 downto 0) := (others=>'0');
  signal admission : std_logic_vector(CHANNEL_COUNT_G-1 downto 0);
begin
  process(clock_i)
    variable settled : boolean;
  begin
    if rising_edge(clock_i) then
      if reset_i='1' then
        previous_pause <= (others=>'0'); applied_pause <= (others=>'0');
        previous_mask <= (others=>'0'); applied_mask <= (others=>'0'); holdoff <= (others=>0);
      else
        settled := true;
        for ch in 0 to CHANNEL_COUNT_G-1 loop
          if calibration_mask_i(ch)/=previous_mask(ch) or pause_mask_i(ch)/=previous_pause(ch) then
            holdoff(ch) <= PIPELINE_CYCLES_G; settled := false;
          elsif holdoff(ch)>0 then
            holdoff(ch) <= holdoff(ch)-1; settled := false;
          end if;
        end loop;
        previous_pause <= pause_mask_i;
        previous_mask <= calibration_mask_i;
        if settled then applied_mask <= calibration_mask_i; applied_pause <= pause_mask_i; end if;
      end if;
    end if;
  end process;
  channels : for ch in 0 to CHANNEL_COUNT_G-1 generate
    admission(ch) <= '1' when reset_i='0' and inhibit_i='0' and
      calibration_mask_i(ch)=previous_mask(ch) and pause_mask_i(ch)='0' and
      pause_mask_i(ch)=previous_pause(ch) and holdoff(ch)=0 else '0';
    self_enable_o(ch) <= self_enable_i and not calibration_mask_i(ch) and admission(ch);
    timing_enable_o(ch) <= (timing_enable_i or calibration_mask_i(ch)) and admission(ch);
    force_trigger_o(ch) <= force_trigger_i and not calibration_mask_i(ch) and admission(ch);
  end generate;
  admission_o <= admission;
  applied_mask_o <= applied_mask;
  pause_applied_o <= applied_pause;
end architecture;
