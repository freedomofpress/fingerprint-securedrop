#!/bin/bash
#
# Run periodically to keep Python requirements up-to-date.
# Usage: ./pip_update.sh

set -e

readonly SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
readonly REQUIREMENTS_DIR="${SCRIPT_DIR}/fpsd/requirements"
readonly VENV="review_env"

# A helper function that prints an error and then exits with failure.
err() {
  echo "ERROR: $@" >&2
  exit 1
}

# This script should not be run with an active virtualenv. Calling deactivate
# does not work reliably, so we require the user do it themself.
if [[ -n "${VIRTUAL_ENV}" ]]; then
  err "Please deactivate your virtualenv before running this script."
fi

hash pip3 virtualenv || err "This script requires pip and virtualenv to run."

# Create a temporary virtualenv for the SecureDrop Python packages in our
# requirements directory.
cd "${REQUIREMENTS_DIR}"

trap "rm -rf ${VENV}" EXIT

virtualenv -p python3 "${VENV}" > /dev/null
source "${VENV}/bin/activate"

pip install -U pip > /dev/null
pip install -U pip-tools > /dev/null

# Compile new requirements (.txt) files from our top-level dependency (.in)
# files. See http://nvie.com/posts/better-package-management/
for r in "crawler" "sorter"; do
  pip-compile -U -o "${r}-requirements.txt" "${r}-requirements.in" > /dev/null
done
