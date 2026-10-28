"""Put the project online as a Hugging Face Space (free, CPU).

Run from the project folder (hr-policy-agent), with the backend venv active:
    pip install -U huggingface_hub
    hf auth login                      (paste a token with "Write" access)
    python deploy/upload_space.py <your-hf-username>/hr-policy-agent

What it does:
  1. creates the Space (Docker type) if it doesn't exist yet
  2. copies GEMINI_API_KEY and JWT_SECRET from backend/.env into the Space's secrets
     (the .env file itself is never uploaded)
  3. uploads the Space settings card as its README
  4. uploads the code, sample policies and your trained router model
The Space then builds by itself (about 10 minutes the first time).
"""
import sys
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
SKIP = [
    "README.md",  # the repo README; the Space gets its own card instead
    "**/.env", ".env", "venv/**", ".venv/**", "**/venv/**", "**/.venv/**", "**/__pycache__/**", "**/*.pyc",
    "**/node_modules/**", "frontend/dist/**", "backend/chroma_db/**", "backend/data/**",
    "backend/checkpoints/**", "**/*.dump", "**/*.zip", ".git/**", ".vscode/**",
]


def main():
    if len(sys.argv) != 2 or "/" not in sys.argv[1]:
        raise SystemExit("Usage: python deploy/upload_space.py <hf-username>/<space-name>")
    space = sys.argv[1]
    api = HfApi()

    env = dotenv_values(ROOT / "backend" / ".env")
    missing = [k for k in ("GEMINI_API_KEY", "JWT_SECRET") if not env.get(k)]
    if missing:
        raise SystemExit(f"backend/.env is missing {', '.join(missing)}")

    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)
    for key in ("GEMINI_API_KEY", "JWT_SECRET"):
        api.add_space_secret(space, key, env[key])
    print("Secrets set (GEMINI_API_KEY, JWT_SECRET)")

    router = ROOT / "backend" / "models" / "router" / "config.json"
    print("Router model:", "included (DistilBERT)" if router.exists()
          else "NOT found, the Space will use the Gemini router instead")

    print("Uploading the project, this can take a few minutes...")
    api.upload_file(repo_id=space, repo_type="space",
                    path_or_fileobj=str(ROOT / "deploy" / "space_README.md"), path_in_repo="README.md",
                    commit_message="Space settings")
    api.upload_folder(repo_id=space, repo_type="space", folder_path=ROOT,
                      ignore_patterns=SKIP, commit_message="Deploy HR Policy Agent")
    name = space.split("/")
    print(f"\nDone. Build log:  https://huggingface.co/spaces/{space}")
    print(f"App (once built): https://{name[0].lower()}-{name[1].lower()}.hf.space")


if __name__ == "__main__":
    main()
