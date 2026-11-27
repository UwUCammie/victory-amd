# Called after checking the GPU and parallel builders in a guarded service.
# Return success while the device or CPU still needs time to settle.
goal30_guard_busy() {
    local kind=$1 runtime_dir=$2 now=$3 stamp
    local gpu="$runtime_dir/goal30-verified-resource-busy"
    local build="$runtime_dir/goal30-verified-build-busy"
    case "$kind" in
        gpu) touch -- "$gpu"; return 0 ;;
        build) touch -- "$build"; return 0 ;;
        idle) ;;
        *) return 2 ;;
    esac
    if stamp=$(stat -c %Y -- "$gpu" 2>/dev/null) && (( now - stamp < 45 )); then
        return 0
    fi
    if stamp=$(stat -c %Y -- "$build" 2>/dev/null) && (( now - stamp < 5 )); then
        return 0
    fi
    return 1
}
