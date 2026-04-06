import os
import sys
import subprocess

def main():
    print("Bootstrapping kiln...")
    # Change to repository root
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    os.chdir(repo_root)

    compiler_path = os.path.join("firescript", "main.py")
    if not os.path.exists(compiler_path):
        print(f"Error: Could not find compiler at {compiler_path}")
        sys.exit(1)

    kiln_entry = os.path.join("kiln", "src", "main.fire")
    if not os.path.exists(kiln_entry):
        print(f"Error: Could not find kiln entry point at {kiln_entry}")
        sys.exit(1)

    output_name = "kiln.exe" if os.name == "nt" else "kiln"

    # Command to run firescript compiler
    cmd = [
        sys.executable,
        compiler_path,
        kiln_entry,
        "-o", output_name
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print(f"Successfully bootstrapped kiln! Binary written to {os.path.join(repo_root, output_name)}")
    else:
        print("Failed to bootstrap kiln.")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
