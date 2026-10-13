ARG BASE_IMAGE=harness-fizzy:rails-ai-evals-168d25f
FROM ${BASE_IMAGE}

USER root
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y python3 && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives

WORKDIR /workspace
