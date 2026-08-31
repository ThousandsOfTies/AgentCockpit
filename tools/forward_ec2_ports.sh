#!/usr/bin/env bash
set -euo pipefail

tool_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$tool_dir/forward_sim_ports.sh" "$@"
