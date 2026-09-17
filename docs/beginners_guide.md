# Beginner's Guide: Erase a File, Then Try to Recover It

This guide is for anyone who wants to use this app, even if you are not
very technical. It explains:

1. What the app does, in plain words
2. How to start it
3. What each tab is for
4. A hands-on practice exercise: delete one photo the normal way, securely
   erase another photo, and then see which one can be recovered

You do **not** need to understand programming. You will need to copy and
paste a few commands into the **Terminal** app. Each command is explained.

> **Tested on:** macOS only. The practice exercise below was run
> step by step on a Mac on 2026-09-17. Linux and Windows are not covered
> here.

---

## Part 1: What does this app do?

When you delete a file normally (Trash, or the `rm` command), the file is
usually **not really gone**. The computer just forgets *where* the file
was, and marks that space as "free to reuse". The actual contents stay on
the disk until something else is written over them. Recovery tools can
often find them.

This app has two sides:

| Side | What it does |
|---|---|
| **Erasing** | Writes random data over a file (or a whole drive) *before* deleting it, so the old contents are replaced with junk. |
| **Recovery** | Scans a disk and tries to find deleted files and bring them back. |

The two sides are meant to be used **together**, to show the difference:
a normally deleted file can often be recovered, a securely erased file
cannot.

> **Important: the Recovery tab is not an "undo" button.**
> If you securely erase a file with this app, it is gone. The Recovery
> tab will not bring it back — that is the whole point of secure
> erasing. The only way to get it back is from a copy somewhere else
> (Time Machine backup, iCloud, the original download, your phone, etc.).
> **Practice only on files you have copies of.**

### Honest limits

- This is a hackathon prototype, not a certified tool.
- On Mac internal drives (SSD, APFS) the overwrite may not land on the
  same physical spot as the original data. The app warns you about this.
- On USB sticks / FAT-formatted disks, the file's **contents** are
  destroyed, but a leftover record of the **file name** can still be
  found (see Part 5).
- More details: [user_manual.md](user_manual.md) and
  [compliance_mapping.md](compliance_mapping.md).

---

## Part 2: Starting the app

Open the **Terminal** app (press `⌘ Space`, type `Terminal`, press Enter)
and run:

```bash
cd ~/Desktop/SIH_149
.venv/bin/python -m app.main
```

- The first line moves Terminal into the project folder. If you put the
  project somewhere else, change the path.
- The second line starts the app.

If it says something is missing, follow the setup steps in the
[README](../README.md) first.

**Keep this Terminal window open** while you use the app — closing it
closes the app.

---

## Part 3: The tabs, explained

| Tab | What it's for |
|---|---|
| **Dashboard** | Overview and recent activity. |
| **Drive Eraser** | Wipes a **whole** drive or disk image. Your Mac's own internal drive is always shown as `BLOCKED` and can never be picked. "Simulation mode" is on by default, which wipes a copy instead of the real thing. |
| **File & Folder Eraser** | Securely erases **individual files or a folder**. Use this for normal files like photos and documents. |
| **Recovery** | Scans a disk image or a plugged-in drive for deleted files. |
| **Audit Log** | A record of everything the app did. **Verify Chain Integrity** checks if anyone edited the record. |
| **Reports** | PDF reports the app created after each erase or scan. |

### "Why can't I select my file?" (greyed-out files)

The **Select Disk Image File...** button (Drive Eraser) and **Browse
Image...** button (Recovery) only show disk image files (`.img`, `.dd`,
`.dmg`) by default. Everything else looks grey.

- That's on purpose — these tabs work on **whole disks**, not single
  photos or documents.
- If you really need another file: at the bottom of the file window,
  click the **"Disk images (*.img *.dd *.dmg)"** dropdown and change it to
  **"All files (*)"**.
- **Want to erase a normal file?** Use the **File & Folder Eraser** tab
  instead. Its file picker shows all files.

---

## Part 4: Practice exercise — erase vs. recover

We will build a small **pretend USB stick** (a "disk image" file on your
Desktop), put two photos on it, remove them in two different ways, and
then scan it.

Using a disk image means **your real drive is never touched**, and you can
throw it away and start again anytime.

**You need:** two picture files (`.jpg` or `.png`) that you have copies of.

> ⚠️ **The order of steps matters.** Do them exactly as written. The
> reason is explained at the end of this part.

### Step 1 — Create the pretend USB stick

In Terminal:

```bash
cd ~/Desktop
dd if=/dev/zero of=demo.img bs=1m count=64
```

This creates an empty 64 MB file called `demo.img` on your Desktop.

### Step 2 — Connect it to your Mac

```bash
hdiutil attach -imagekey diskimage-class=CRawDiskImage -nomount demo.img
```

It prints a name like **`/dev/disk4`**. **Write this down** — the number
may be different on your Mac. We'll call it `/dev/diskN` below; always
replace it with your real one.

You may also see:
```
hdiutil: WARNING: 'hdiutil attach -nomount ...' is deprecated.
```
**Ignore this.** It's just a notice, the command still worked.

### Step 3 — Double-check you have the right disk

This step protects you from formatting the wrong disk by accident.

```bash
diskutil list /dev/diskN
```

It **must** say `(disk image)` and a size of about **67.1 MB**, like:

```
/dev/disk4 (disk image):
   0:                          +67.1 MB    disk4
```

🛑 **If it says anything else (like `internal` or `external, physical`,
or a size in GB), STOP.** You typed the wrong number. Go back to Step 2.

### Step 4 — Format it

```bash
diskutil eraseVolume MS-DOS DEMOVOL /dev/diskN
```

This formats the pretend stick (like a real USB stick) and names it
`DEMOVOL`. It now appears in Finder and at `/Volumes/DEMOVOL`.

### Step 5 — Copy two photos onto it

```bash
cp "/path/to/your/first picture.png" /Volumes/DEMOVOL/photo1.png
cp "/path/to/your/second picture.jpg" /Volumes/DEMOVOL/photo2.jpg
sync
```

Tips:
- **Always put the path in quotes** `"..."`. File names with spaces
  (like `Screenshot 2026-09-17 at 18.42.51.png`) break without quotes and
  give a confusing `Not a directory` error.
- **Easiest way to get a path:** type `cp ` (with a space), then **drag the
  file from Finder into the Terminal window**. Terminal fills in the path
  for you.
- **Keep the real extension.** A `.jpg` should stay `.jpg`, a `.png` should
  stay `.png`.
- `sync` makes sure everything is really saved to the disk.

Check it worked:

```bash
ls /Volumes/DEMOVOL
```

You should see `photo1.png` and `photo2.jpg`. (macOS also adds hidden
files starting with `._` — that's normal, ignore them.)

### Step 6 — Securely erase photo2 (in the app)

1. In the app, open the **File & Folder Eraser** tab.
2. Click **Add Files...**
3. In the file window, press **⌘ ⇧ G** (Command + Shift + G), type
   `/Volumes/DEMOVOL`, press Enter.
4. Select **photo2.jpg** and click **Open**.
5. Click **Securely Erase Queue**.
6. In the confirmation window, type exactly `ERASE FILES`, tick the
   checkbox, and click **OK**.
7. You'll see `Erase complete — PASS`. A warning window about filesystem
   limits may pop up — that's expected, read it and close it.

**If photo2.jpg is greyed out and you can't select it:** macOS may be
blocking the app from reading removable disks. Go to **System Settings →
Privacy & Security → Files & Folders → Terminal** and turn on
**Removable Volumes**. Then quit the app, start it again (Part 2), and
retry.

### Step 7 — Delete photo1 the normal way

Back in Terminal:

```bash
rm /Volumes/DEMOVOL/photo1.png
sync
```

Use `rm`, **not** Finder's "Move to Trash". Finder only moves it to a
hidden Trash folder on the same disk, so it isn't really deleted.

### Step 8 — Disconnect the pretend stick

```bash
diskutil eject /dev/diskN
```

**Do this right away** after Step 7. Don't copy anything else onto the
stick first. Ejecting makes sure everything is saved into `demo.img`.

### Step 9 — Scan it for deleted files

1. In the app, open the **Recovery** tab.
2. Click **Browse Image...** and pick **demo.img** on your Desktop.
3. Click **Start Recovery Scan**. On a 64 MB image this takes a few
   seconds.

### Step 10 — Read the results

What we saw when we tested this:

| What you'll see | What it means |
|---|---|
| `_hoto1.png` (engine **pytsk3**), type **PNG**, confidence **100** | ✅ **photo1 recovered!** The first letter is replaced by `_` because that's how FAT marks a file as deleted. |
| `f000….png` (engine **photorec**), same size, type **PNG** | ✅ **photo1 again**, found a second way (by searching for picture data). Same SHA-256 = identical file. |
| `_hoto2.jpg` and a random name like `ktrvjgwx7ul31092`, type **unknown**, confidence **20 (low)** | ❌ **photo2 — erased.** The entries still exist, but the contents are random junk. It won't open as a picture. |
| Names starting with `._`, `.gz` files, `.apple` files | Leftover macOS system/housekeeping data. Ignore. |

To **prove** photo1 came back: click its row, click **Export Selected
File...**, save it to your Desktop, and open it. It's your picture.

Try the same with photo2's rows — the exported file won't open as an
image.

**The engines explained:**
- **pytsk3** reads the disk's "table of contents" to find deleted entries.
- **photorec** ignores the table of contents and scans raw data looking
  for patterns that look like the start of a picture, PDF, etc.
- If the status line says `engines unavailable: bulk_extractor`, that's
  fine — that optional tool just isn't installed. It only fills the
  "PII / Metadata Artifacts" table.

### Why the order matters

On FAT disks (USB sticks), new data is written into the **first free
space**. When you delete photo1, its space becomes free. If you then erase
photo2 in the app, the app creates small new entries on the disk — and
they land **exactly on the start of photo1**, destroying its header.
Without the header, photo1 can't be recognized or recovered.

So: **erase first, delete normally last, eject immediately.**

We learned this the hard way — in the wrong order, 99.9% of photo1's data
was still on the disk, but neither recovery engine could find it.

### Starting over

```bash
rm ~/Desktop/demo.img
```

Then go back to Step 1. (Make sure it's ejected first — Step 8.)

---

## Part 5: Things that surprise people

- **The erased file's name can still show up.** In Step 10, `_hoto2.jpg`
  still shows most of photo2's original name. On FAT disks, the app
  renames the file before deleting it, but FAT keeps a deleted record of
  the old name anyway. The **contents** are destroyed; the **name** is not
  fully hidden.
- **Type "unknown" with low confidence** is what an erased file *should*
  look like — random data isn't any known file type.
- **Confidence scores** only compare results within the same scan. "100"
  does not mean "100% guaranteed".
- **Scanning your Mac's internal drive** won't work well. It needs special
  permissions, and Mac SSDs clean up deleted space quickly on their own.
  Use disk images or USB sticks for practice.

---

## Part 6: Quick troubleshooting

| Problem | Fix |
|---|---|
| `cp: ... Not a directory` | The file path has spaces. Put it in quotes, or drag the file into Terminal. |
| `No such file or directory` | Typo in the path or wrong extension (e.g. `.jpg` vs `.png`). Run `ls /Volumes/DEMOVOL` to see real names. |
| `/Volumes/DEMOVOL` doesn't exist | You skipped Step 4 (format), or the image was already ejected. |
| `diskutil image attach ... doesn't exist` | Don't use `diskutil image attach`. Use the `hdiutil attach` command from Step 2 exactly. |
| Files greyed out in the File & Folder Eraser | See the note at the end of Step 6 (Removable Volumes permission). |
| Files greyed out in Drive Eraser / Recovery | Change the dropdown to "All files (*)" — see Part 3. |
| Recovery finds nothing from the normally deleted file | Steps were done out of order, or something was copied onto the stick after deleting. Start over. |
| Recovery shows 0 results at all | Check the status line for `engines unavailable`. If both `pytsk3` and `photorec` are listed, the setup is incomplete — see the README. |
