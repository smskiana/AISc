import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export class GitRevisionProvider {
  /** Reads the current repository revision without changing Git state. */
  public async getRevision(): Promise<string> {
    const { stdout } = await execFileAsync("git", ["rev-parse", "HEAD"], { cwd: this.root });
    return stdout.trim();
  }

  public constructor(private readonly root: string) {}
}
