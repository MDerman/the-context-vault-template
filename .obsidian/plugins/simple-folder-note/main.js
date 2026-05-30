const { Plugin, TFolder, TFile } = require('obsidian');

class SimpleFolderNotePlugin extends Plugin {
  async onload() {
    this.styleEl = document.head.createEl('style');
    this.styleEl.id = 'simple-folder-note-style';

    this.app.workspace.onLayoutReady(() => this.refresh());

    this.registerEvent(this.app.vault.on('create', () => this.refresh()));
    this.registerEvent(this.app.vault.on('delete', () => this.refresh()));
    this.registerEvent(this.app.vault.on('rename', () => this.refresh()));

    // capture 단계에서 가로채서 기본 동작(폴더 접기/펼치기)보다 먼저 처리
    this.registerDomEvent(document, 'click', (evt) => this.handleClick(evt), { capture: true });
  }

  onunload() {
    this.styleEl?.remove();
  }

  // 폴더의 모든 폴더 노트 후보: 안쪽(folder/folder.md) + 바깥쪽(parent/folder.md)
  getFolderNotes(folder) {
    if (!(folder instanceof TFolder)) return [];
    if (folder.path === '/' || folder.path === '') return [];

    const notes = [];

    // 안쪽: folder/folder.md
    const insidePath = `${folder.path}/${folder.name}.md`;
    const inside = this.app.vault.getAbstractFileByPath(insidePath);
    if (inside instanceof TFile) notes.push(inside);

    // 바깥쪽: 폴더와 같은 레벨의 folder.md
    const outsidePath = `${folder.path}.md`;
    const outside = this.app.vault.getAbstractFileByPath(outsidePath);
    if (outside instanceof TFile) notes.push(outside);

    return notes;
  }

  // 폴더 클릭 시 열 우선 노트 (안쪽 → 바깥쪽 순)
  getFolderNote(folder) {
    return this.getFolderNotes(folder)[0] || null;
  }

  // 모든 폴더 노트를 CSS 로 숨김 (안쪽/바깥쪽 모두)
  refresh() {
    const paths = [];
    for (const f of this.app.vault.getAllLoadedFiles()) {
      if (f instanceof TFolder) {
        for (const note of this.getFolderNotes(f)) {
          paths.push(note.path);
        }
      }
    }

    const rules = paths.map(p => {
      const escaped = p.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
      return `.nav-file-title[data-path="${escaped}"] { display: none !important; }`;
    }).join('\n');

    this.styleEl.textContent = rules;
  }

  handleClick(evt) {
    const titleEl = evt.target.closest('.nav-folder-title');
    if (!titleEl) return;

    const clickedCollapseIcon = evt.target.closest(
      '.nav-folder-collapse-indicator, .collapse-icon, .tree-item-icon'
    );
    if (clickedCollapseIcon && titleEl.contains(clickedCollapseIcon)) return;

    const folderPath = titleEl.getAttribute('data-path');
    if (!folderPath) return;

    const folder = this.app.vault.getAbstractFileByPath(folderPath);
    const note = this.getFolderNote(folder);
    if (!note) return;

    // 이미 그 노트가 활성 탭이면 중복 오픈 방지
    const activeFile = this.app.workspace.getActiveFile();
    if (activeFile && activeFile.path === note.path) return;

    this.app.workspace.getLeaf(false).openFile(note);
  }
}

module.exports = SimpleFolderNotePlugin;
