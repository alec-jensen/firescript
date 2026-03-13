import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;
let outputChannel: vscode.OutputChannel;
let extensionContext: vscode.ExtensionContext;

function startClient(): void {
  const config = vscode.workspace.getConfiguration("firescript");
  const useUv: boolean = config.get("useUv", true);

  // Resolve workspace root for the cwd of the server process.
  const workspaceFolders = vscode.workspace.workspaceFolders;
  const workspaceRoot = workspaceFolders ? workspaceFolders[0].uri.fsPath : "";
  outputChannel.appendLine(`Workspace root: "${workspaceRoot}"`);

  // Resolve the path to lsp_server.py.
  let serverScript: string = config.get("serverPath", "");
  if (!serverScript) {
    // Search in order: packaged location, compatibility shim, then relative to the extension install dir.
    const candidates = [
      path.join(workspaceRoot, "firescript", "lsp", "lsp_server.py"),
      path.join(workspaceRoot, "firescript", "lsp_server.py"),
      path.join(extensionContext.extensionPath, "..", "..", "firescript", "lsp", "lsp_server.py"),
      path.join(extensionContext.extensionPath, "..", "..", "firescript", "lsp_server.py"),
    ];
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) {
        serverScript = candidate;
        break;
      }
      outputChannel.appendLine(`Not found: ${candidate}`);
    }
  }

  if (!serverScript || !fs.existsSync(serverScript)) {
    const msg = `firescript: could not find firescript/lsp/lsp_server.py. Set "firescript.serverPath" in settings to point to it.`;
    outputChannel.appendLine(msg);
    vscode.window.showErrorMessage(msg);
    return;
  }

  outputChannel.appendLine(`Server script: ${serverScript}`);
  outputChannel.appendLine(`Using uv: ${useUv}`);

  // Build the server launch command.
  const command = useUv ? "uv" : "python";
  const args = useUv
    ? ["run", "python", serverScript, "--stdio"]
    : [serverScript, "--stdio"];

  outputChannel.appendLine(`Command: ${command} ${args.join(" ")}`);
  outputChannel.appendLine(`CWD: ${workspaceRoot || "(none)"}`);

  const serverOptions: ServerOptions = {
    run: {
      command,
      args,
      options: { cwd: workspaceRoot || undefined },
      transport: TransportKind.stdio,
    },
    debug: {
      command,
      args,
      options: { cwd: workspaceRoot || undefined },
      transport: TransportKind.stdio,
    },
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "firescript" }],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.fire"),
    },
    outputChannel,
  };

  client = new LanguageClient(
    "firescript",
    "firescript Language Server",
    serverOptions,
    clientOptions
  );

  client.start().then(() => {
    outputChannel.appendLine("Language server started successfully.");
  }).catch((err: unknown) => {
    const msg = `firescript language server failed to start: ${err}`;
    outputChannel.appendLine(msg);
    vscode.window.showErrorMessage(msg);
  });
}

export function activate(context: vscode.ExtensionContext): void {
  extensionContext = context;
  outputChannel = vscode.window.createOutputChannel("firescript Language Server");
  context.subscriptions.push(outputChannel);
  outputChannel.appendLine("firescript extension activating...");

  const restartCommand = vscode.commands.registerCommand("firescript.restartLanguageServer", async () => {
    outputChannel.appendLine("Restarting language server...");
    if (client) {
      await client.stop();
      client = undefined;
    }
    startClient();
  });
  context.subscriptions.push(restartCommand);

  startClient();

  context.subscriptions.push({ dispose: () => client?.stop() });
}

export function deactivate(): Thenable<void> | undefined {
  return client?.stop();
}
