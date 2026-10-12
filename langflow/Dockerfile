# Langflow with tutor_core installed in the Python environment Langflow itself runs on (M3).
#
# Build context is ./tutor_core (see docker-compose.yml), so only the package is sent to the builder.
#
# NOT verified by the author: the base image's user and Python layout (it could not be built where this was written).
# The build is therefore written to FAIL LOUDLY rather than yield an image whose tools cannot import tutor_core:
#   * it prints which interpreter it installs into and checks the user exists;
#   * its last step imports everything the tools need AS THE USER THE CONTAINER RUNS AS, with the interpreter the
#     container uses. If that fails, the build fails.
# Find the base image's values with:
#   docker run --rm --entrypoint sh langflowai/langflow:1.12.2 -c 'id; command -v python; python --version'
FROM langflowai/langflow:1.12.2

# The user the base image runs as (the official image uses "user"). Override: LANGFLOW_RUN_AS_USER in .env.
ARG RUN_AS_USER=user

USER root
COPY . /tmp/tutor_core
RUN set -eux; \
    PY="$(command -v python)"; \
    echo "Installing tutor_core into: ${PY}"; \
    "${PY}" --version; \
    id "${RUN_AS_USER}"; \
    ( "${PY}" -m pip install --no-cache-dir /tmp/tutor_core \
      || uv pip install --python "${PY}" --no-cache /tmp/tutor_core ); \
    rm -rf /tmp/tutor_core
USER ${RUN_AS_USER}

RUN python -c "import sys, tutor_core, psycopg2, langflow; print('tutor_core OK for', sys.executable, 'from', tutor_core.__file__)"
