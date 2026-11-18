#!/bin/bash
set -euo pipefail

if [[ -n "${SSH_KEY:-}" && -f "$SSH_KEY" ]]; then
  rm -f -- "$SSH_KEY"
fi
if [[ -n "${SSH_KNOWN_HOSTS:-}" && -f "$SSH_KNOWN_HOSTS" ]]; then
  rm -f -- "$SSH_KNOWN_HOSTS"
fi
