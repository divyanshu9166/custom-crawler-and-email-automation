# Python base-image registry recovery

The Ubuntu VPS reported a successful Docker Hub DNS lookup followed by an HTTPS connection
failure to an IPv6 address: `connect: network is unreachable`. That is a distinct failure
from its earlier DNS timeout. An already-healthy application can still be running its older
image when a new build fails; health alone does not establish the deployed source revision.

Both application Dockerfiles accept `PYTHON_BASE_IMAGE` as a build argument. Their default
remains `python:3.13-slim-bookworm`. A one-build override can use the same version/distribution
tag from ECR Public without changing host DNS, disabling host IPv6, restarting the Docker
daemon, editing global registry configuration or replacing the application data volume.
AWS documents this Python image namespace in its
[Docker example](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/docker-quickstart.html).

On 17 October 2026 an anonymous token request and a live manifest request for
`public.ecr.aws/docker/library/python:3.13-slim-bookworm` both returned HTTP 200 from the
development machine. The manifest included Linux amd64 (the user's VPS architecture) and
arm64. This verifies source availability at check time, not registry reachability from the
VPS, a completed Docker build, byte-identical synchronization with Docker Hub, or access
to the subsequent pip/apt/Playwright download hosts. No local Docker runtime is available.

## Existing headed-browser deployment

Keep Worker and Sending OFF while updating. In the existing project directory, pull the
new Dockerfile before using the override:

```sh
git pull --ff-only
```

Build and start only if the build succeeds:

```sh
sudo docker compose -f compose.yaml -f compose.platform-browser.yaml build --build-arg PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.13-slim-bookworm app && sudo docker compose -f compose.yaml -f compose.platform-browser.yaml up -d --no-build --wait --wait-timeout 120 app
```

```sh
curl -fsS --max-time 10 http://127.0.0.1:8000/health
```

The override applies only to this build; use it again for subsequent builds while the
Docker Hub path remains unavailable. Both Compose files and the existing `/data` volume
are preserved. A future browser-setup image build can use the same build argument.

If the build fails again, inspect the failing hostname/stage. A new error from ECR, Debian,
PyPI or Playwright is a separate network/source check, not evidence that the IPv6 route or
all networking has been repaired. Retain the complete error and the current healthy app.
