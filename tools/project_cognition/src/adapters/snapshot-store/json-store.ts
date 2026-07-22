import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { emptySnapshot, ProjectSnapshot } from "../../domain/model.js";

export class JsonSnapshotStore {
  public constructor(private readonly root: string) {}

  /** Loads the current snapshot, creating the root snapshot when absent. */
  public async load(projectId: string): Promise<ProjectSnapshot> {
    try { return JSON.parse(await readFile(this.currentPath(projectId), "utf8")) as ProjectSnapshot; }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      const snapshot = emptySnapshot(projectId);
      await this.commit(snapshot, undefined);
      return snapshot;
    }
  }

  /** Atomically commits a snapshot and preserves one rollback version. */
  public async commit(snapshot: ProjectSnapshot, expectedBaseId?: string): Promise<void> {
    await mkdir(this.root, { recursive: true });
    const currentPath = this.currentPath(snapshot.projectId);
    let current: ProjectSnapshot | undefined;
    try { current = JSON.parse(await readFile(currentPath, "utf8")); } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
    if (expectedBaseId && current?.id !== expectedBaseId) throw new Error("BASE_SNAPSHOT_CONFLICT");
    if (current) await writeFile(this.previousPath(snapshot.projectId), JSON.stringify(current, null, 2), "utf8");
    const temporary = `${currentPath}.${process.pid}.tmp`;
    await writeFile(temporary, JSON.stringify(snapshot, null, 2), "utf8");
    await rename(temporary, currentPath);
  }

  /** Restores the previous snapshot as a new atomic head. */
  public async rollback(projectId: string): Promise<ProjectSnapshot> {
    const previous = JSON.parse(await readFile(this.previousPath(projectId), "utf8")) as ProjectSnapshot;
    await this.commit(previous);
    return previous;
  }

  private currentPath(projectId: string): string { return path.join(this.root, `${projectId}.json`); }
  private previousPath(projectId: string): string { return path.join(this.root, `${projectId}.previous.json`); }
}
