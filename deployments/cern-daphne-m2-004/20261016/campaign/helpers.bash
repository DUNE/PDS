_vst_m2_pds() {
    PYTHONPATH="$PDS_PROTOBUF_DIR:$PDS_CHECKOUT/src${PYTHONPATH:+:$PYTHONPATH}" "$@"
}
vst_use() {
    case "${1:-calibration}" in calibration|tp-test) export VST_PROFILE=${1:-calibration};; *) return 2;; esac
    export DAPHNE_CFG="$VST_M2_ROOT/config/$VST_PROFILE"
    export DAQ_INPUT="$VST_M2_ROOT/data/$VST_PROFILE/raw"
    export DUNEDAQ_DB_PATH="$DAPHNE_CFG:$VST_DAQ_DB_PATH"
}
vst_help() { cat "$VST_M2_ROOT/COMMANDS.txt"; }
vst_blockers() { "$PDS_VENV/bin/python" "$VST_M2_ROOT/check-draft.py"; }
vst_plan() { _vst_m2_pds "$PDS_VENV/bin/pds-calibrate" plan "$PDS_PLAN"; }
daphne_status() { _vst_m2_pds "$PDS_VENV/bin/python" "$VST_M2_ROOT/board-status.py" "$@"; }
vst_validate() { _vst_m2_pds "$PDS_VENV/bin/python" "$VST_M2_ROOT/validate-config.py" "$VST_M2_ROOT/validation.json"; }
vst_daq() {
    vst_blockers || return
    daphne_status --require-timing || return
    source /nfs/home/np04daq/bin/web_proxy.sh -u || return
    drunc-unified-shell ssh-CERN-kafka.json "$DAPHNE_CFG/sessions/pds-vst-session.data.xml" pds-m2-004 "$VST_SESSION"
}
vst_calibrate() {
    [[ $# == 2 && "$VST_PROFILE" == calibration && -d "$DAQ_INPUT" ]] || { printf 'vst_calibrate NEW_RESULT_DIR NEW_JOURNAL (calibration profile, with DAQ running)\n' >&2; return 2; }
    vst_blockers || return
    daphne_status --require-ready || return
    _vst_m2_pds "$PDS_VENV/bin/pds-calibrate" run "$PDS_PLAN" --input-dir "$DAQ_INPUT" --output-dir "$1" --journal "$2"
}
