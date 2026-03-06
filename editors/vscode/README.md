# Firescript VS Code Extension (local development)

## Reload in VS Code
- Open the Command Palette and run: **Developer: Reload Window**
- If testing the extension host, use **Developer: Reload Window** or press `F5` from the `editors/vscode` extension workspace to launch a new Extension Host.

## Build a VSIX (package and reinstall)
1. Install dependencies: `npm install`
2. Compile the extension: `npm run compile`
3. Package the extension as a VSIX (uses `vsce`):
   - If you have `vsce` globally: `vsce package`
   - Or via npx: `npx vsce package`
4. Install the produced VSIX file (example filename):
   `code --install-extension firescript-0.1.0.vsix`

## Quick verification
- Open a `.fire` file (for example `tests/sources/invalid/array_errors.fire`).
- Reload the window and the file icon should show the Firescript logo and diagnostics / token colouring should reflect the updated grammar.

If you want, I can create the VSIX for you now and show the exact install command output.
