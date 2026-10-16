library ieee;
use ieee.std_logic_1164.all;
use work.daphne_subsystem_pkg.all;

-- Ethernet readout policy for frontend register 0x34. The selector is already
-- coherently synchronized by frontend_common into clock_i.
entity readout_trigger_policy is
  port (
    clock_i : in std_logic;
    source_i : in std_logic_vector(2 downto 0);
    inhibit_i : in std_logic;
    software_trigger_i, hardware_trigger_i : in std_logic;
    admission_enable_o, self_trigger_enable_o, timing_trigger_enable_o, force_trigger_o : out std_logic;
    calibration_tag_o : out std_logic_vector(1 downto 0)
  );
end entity;

architecture rtl of readout_trigger_policy is
  signal previous_source_s : std_logic_vector(2 downto 0) := "011";
  signal admission_enable_s, software_selected_s, hardware_selected_s : std_logic;
begin
  process(clock_i)
  begin
    if rising_edge(clock_i) then previous_source_s <= source_i; end if;
  end process;
  -- A source transition cancels the old continuation chain through enable_i,
  -- without clearing queued frames or resetting the sample ring/serializer.
  admission_enable_s <= not inhibit_i when source_i = previous_source_s and (source_i = "000" or source_i = "001" or source_i = "010" or source_i = "011" or source_i = "100") else '0';
  software_selected_s <= software_trigger_i when source_i = "000" or source_i = "011" else '0';
  hardware_selected_s <= hardware_trigger_i when source_i = "001" or source_i = "011" else '0';
  admission_enable_o <= admission_enable_s;
  self_trigger_enable_o <= admission_enable_s when source_i = "010" or source_i = "011" else '0';
  timing_trigger_enable_o <= admission_enable_s when source_i = "100" or source_i = "011" else '0';
  force_trigger_o <= (software_selected_s or hardware_selected_s) and admission_enable_s;
  -- Software wins simultaneous accepted software/BNC triggers in combined mode.
  calibration_tag_o <= CALIBRATION_TAG_SOFTWARE_C when software_selected_s = '1' and admission_enable_s = '1' else
                       CALIBRATION_TAG_BNC_C when hardware_selected_s = '1' and admission_enable_s = '1' else
                       CALIBRATION_TAG_NORMAL_C;
end architecture;
