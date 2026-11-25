from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]

IMAGES = [
    ("eaicsp/platform:local", "services/platform/Dockerfile", "services/platform"),
    ("eaicsp/inventory:local", "services/inventory/Dockerfile", "services/inventory"),
    ("eaicsp/logistics:local", "services/logistics/Dockerfile", "services/logistics"),
    ("eaicsp/compliance:local", "services/compliance/Dockerfile", "services/compliance"),
    ("eaicsp/supplier-portal:local", "services/supplier-portal/Dockerfile", "services/supplier-portal"),
    ("eaicsp/api-gateway:local", "services/api-gateway/Dockerfile", "services/api-gateway"),
    ("eaicsp/eta-consumer:local", "ml-services/eta-prediction/Dockerfile", "."),
    ("eaicsp/anomaly-detection:local", "ml-services/anomaly-detection/Dockerfile", "."),
    ("eaicsp/minio-with-client:local", "infra/minio/Dockerfile", "infra/minio"),
]


def main():
    for image, dockerfile, context in IMAGES:
        dockerfile_path = ROOT / dockerfile
        context_path = ROOT / context

        if not dockerfile_path.is_file():
            raise RuntimeError(f"Dockerfile missing: {dockerfile}")
        if not context_path.is_dir():
            raise RuntimeError(f"Build context missing: {context}")

        print(f"\n========== Building {image} ==========", flush=True)
        command = [
            "docker", "build",
            "-t", image,
            "-f", str(dockerfile_path),
            str(context_path),
        ]
        subprocess.run(command, cwd=ROOT, check=True)

    print("\nAll nine local images built successfully.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"IMAGE BUILD FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
