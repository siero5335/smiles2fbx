# smiles2fbx

SMILES → FBX ワンライナー変換ツール（Unity想定）

OpenBabel不要・Blenderアドオン不要。RDKitで3D座標と結合情報を生成し、Blenderの標準bpy APIでメッシュを構築してFBXをエクスポートします。化学構造の最適化は考慮していません。

## 必要環境

- **Python 3.8+** , **RDKit**
- **Blender 4.x**（コマンドラインから呼び出せること, 3.x未確認）

## 動作確認状況

- **確認済み**: macOS + Python 3 + RDKit + Blender 4.5 LTS
- **未確認**: Linux / Windows / WSL / Git Bash

Linux や Windows 系でも動く想定ですが、このリポジトリでは現時点で macOS 以外の実機確認はしていません。
そのため、他環境では Blender の headless 起動、RDKit の導入方法、シェルからの `bash` 実行方法を個別に調整する必要がある可能性があります。

### インストール例

```bash
# RDKit (pip)
pip install rdkit

# RDKit (conda — より安定)
conda install -c conda-forge rdkit

# Blender はパッケージマネージャか公式サイトからインストール
# https://www.blender.org/download/
```

### Blender のパス設定

Blender は次の順で探索されます。

1. `BLENDER_PATH` 環境変数
2. `PATH` 上の `blender`
3. macOS の標準配置 `/Applications/Blender.app/Contents/MacOS/Blender`

`PATH` に通す場合は次の設定が使えます。

```bash
export PATH="/Applications/Blender.app/Contents/MacOS:$PATH"
blender --version
```

`PATH` を使わない場合は `BLENDER_PATH` で明示指定してください。

```bash
# macOS
export BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender

# Linux (snap)
export BLENDER_PATH=/snap/bin/blender

# Linux (deb/rpm など)
export BLENDER_PATH=/usr/bin/blender

# Windows (WSL / Git Bash)
export BLENDER_PATH="/mnt/c/Program Files/Blender Foundation/Blender 4.2/blender.exe"
```

### OS 別メモ

**macOS**

- `~/.zshrc` に `BLENDER_PATH` または `PATH` を設定すればそのまま使えます
- Blender headless が不安定な場合は LTS 版の利用を推奨します

**Linux**

- `python3`、RDKit、Blender CLI が入っていれば動く想定です
- Blender の場所は `/usr/bin/blender`、`/snap/bin/blender` など環境差があります
- この環境は未実機確認です

**Windows (WSL / Git Bash)**

- このスクリプトは `sh` / `bash` 前提なので、PowerShell や `cmd.exe` 単体ではなく WSL か Git Bash での利用を想定しています
- Blender 本体は Windows 側に入れ、`BLENDER_PATH` で `.exe` を指す運用を想定しています
- パスに空白が入るため、`BLENDER_PATH` は必ずクォートしてください
- この環境は未実機確認です

## 使い方

### 単発変換

```bash
chmod +x smiles2fbx.sh
./smiles2fbx.sh <SMILES> <output.fbx> [options]
```

`bash` で直接呼ぶ場合:

```bash
bash smiles2fbx.sh <SMILES> <output.fbx> [options]
```

#### 基本例

```bash
# Stickモデル（デフォルト：棒のみ、元素色CPK配色）
./smiles2fbx.sh "c1ccccc1" benzene.fbx

# 水素を省略（スッキリ＆軽量）
./smiles2fbx.sh "CCO" ethanol.fbx --no-hydrogen

# Ball-and-Stick モデル
./smiles2fbx.sh "CCO" ethanol.fbx --mode ball-and-stick
```

#### モノクローム出力

```bash
# シルバー（デフォルト）
./smiles2fbx.sh "c1ccccc1" benzene.fbx --mono --no-hydrogen

# ゴールド
./smiles2fbx.sh "c1ccccc1" benzene.fbx --mono FFD700

# マットブラック
./smiles2fbx.sh "c1ccccc1" benzene.fbx --mono 1A1A1A --roughness 0.8 --metallic 0.3

# ローズゴールド
./smiles2fbx.sh "c1ccccc1" benzene.fbx --mono B76E79 --metallic 0.85 --roughness 0.2
```

#### 見た目の調整

```bash
# 棒を細くする
./smiles2fbx.sh "CCO" ethanol.fbx --radius 0.10

# VRChat向けにスケール縮小
./smiles2fbx.sh "CCO" ethanol.fbx --scale 0.3

# ポリゴンをさらに削減（segments=6）
./smiles2fbx.sh "CCO" ethanol.fbx --segments 6
```

#### RDKit オプション例

RDKit のコンフォメーション生成シードを変えたい場合:

```bash
./smiles2fbx.sh "CCO" ethanol.fbx --seed 12345
```

巨大分子向けに埋め込みを軽くしたい場合:

```bash
./smiles2fbx.sh "CCO" ethanol.fbx --largest-fragment --skip-add-hs --embed-retries 8
```

3D 埋め込みが失敗したときも平面的な座標で出力したい場合:

```bash
./smiles2fbx.sh "CCO" ethanol.fbx --allow-2d-fallback
```

### CSV バッチ変換

```bash
python3 smiles2fbx_batch.py molecules.csv out_fbx -- --mono --segments 6
```

CSV は少なくとも `smiles` 列が必要です。`name` と `feature` は任意で、あれば出力ファイル名に使われます。

例:

```csv
name,smiles,feature
benzene,c1ccccc1,ring
ethanol,CCO,alcohol
```

この例では `out_fbx/benzene__ring.fbx` のような名前で出力されます。
`feature` が空なら `name.fbx`、`name` も空なら `row_0001.fbx` のような連番名になります。

列名は自動検出しますが、必要なら明示指定できます。

```bash
python3 smiles2fbx_batch.py compounds.csv out_fbx \
  --name-column 名前 \
  --smiles-column SMILES \
  --feature-column 特徴 \
  -- --mono
```

バッチ実行結果は既定で `out_fbx/batch_results.csv` に保存されます。

#### バッチオプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| `--name-column NAME` | *(auto detect)* | 名前列を明示指定 |
| `--smiles-column NAME` | *(auto detect)* | SMILES列を明示指定 |
| `--feature-column NAME` | *(auto detect)* | 特徴列を明示指定 |
| `--results-csv PATH` | `<outdir>/batch_results.csv` | 結果CSVの出力先 |
| `--overwrite` | *(off)* | 同名 `.fbx` を上書きする |
| `--stop-on-error` | *(off)* | 最初の失敗行で中断する |

`--` 以降の引数は各行の `smiles2fbx.sh` 呼び出しへそのまま渡されます。

## 単発変換オプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| `--segments N` | `8` | シリンダー/球の分割数。低いほど軽量 |
| `--scale F` | `1.0` | 全体スケール |
| `--radius F` | `0.2` | 棒の太さ |
| `--mode MODE` | `stick` | `stick`（棒のみ）または `ball-and-stick` |
| `--seed N` | `61453` | RDKit の 3D コンフォメーション生成シード |
| `--embed-retries N` | `1` | RDKit の 3D 埋め込み再試行回数 |
| `--largest-fragment` | *(off)* | 塩や複数断片を含む入力から最大断片だけを使う |
| `--skip-add-hs` | *(off)* | RDKit の `AddHs()` を省略して軽量化する |
| `--allow-2d-fallback` | *(off)* | 3D 埋め込み失敗時に 2D 座標で続行する |
| `--no-hydrogen` | *(表示)* | 水素原子と結合を非表示 |
| `--mono [HEX]` | *(CPK配色)* | モノクローム出力。HEX省略時はシルバー `C0C0C0` |
| `--metallic F` | `0.1` / mono時 `0.9` | PBR Metallic 値（0.0〜1.0） |
| `--roughness F` | `0.4` / mono時 `0.15` | PBR Roughness 値（0.0〜1.0） |

補足:

- `--largest-fragment` は最大の disconnected fragment を 1 つだけ残します。塩や対イオンを落としたいとき向けです
- `--skip-add-hs` を使うと RDKit 側で暗黙水素を明示化しないため、埋め込みは軽くなりますが、水素表示は基本的に出なくなります
- `--embed-retries 1` は「再試行なし」で、合計1回だけ埋め込みを試します
- `--embed-retries` は `--seed` から連番で seed をずらしながら再試行します
- `--allow-2d-fallback` を使うと、巨大分子などで 3D 埋め込みに失敗した場合でも平面的な 2D 座標で FBX 化を続行します
- 2D フォールバック時は力場最適化をスキップします

## ファイル構成

```text
smiles2fbx/
├── smiles2fbx.sh         # 単発変換エントリポイント（シェルスクリプト）
├── smiles2fbx_batch.py   # CSVバッチ変換スクリプト
├── mol_to_fbx.py         # Blender Python スクリプト（molecule JSON→FBX）
└── README.md
```

## 処理フロー

```text
単発:
SMILES  ──(RDKit)──▶  molecule JSON  ──(Blender headless)──▶  FBX
                      3D座標生成         bpyでメッシュ構築
                      力場最適化         マテリアル設定
                      結合情報生成       FBXエクスポート

バッチ:
CSV  ──(smiles2fbx_batch.py)──▶  行ごとに smiles2fbx.sh を呼び出し
                                  結果を batch_results.csv に記録
```

## VRChat 向けメモ

- **Stickモデル推奨** — ボールなしでポリゴン数が大幅に少ない
- **`--no-hydrogen`** で水素を消すとさらに軽量化
- **`--segments 6`** まで下げても見た目は十分
- CPK配色（デフォルト）では棒が中点で分割され、各半分が原子の元素色で着色される
- 芳香族結合は見た目簡略化のため単結合相当の棒として出力される
- モノクローム時は分割なし（1ボンド=1シリンダー）でさらに軽量
- 巨大分子では `--largest-fragment --skip-add-hs --no-hydrogen --mono --segments 6` の組み合わせが最も通しやすい
- それでも 3D 化できない場合は `--allow-2d-fallback` で平面的な出力に逃がせます
- Unity 側でマテリアルを **lilToon** 等の VRChat 対応シェーダーに差し替え推奨
- 大きい分子は `--scale 0.3` 程度にしないとワールド内で巨大になる
- VRChat の Performance Rank を意識する場合、ポリゴン数 10,000 以下を目安に

## トラブルシューティング

**`blender: command not found`**
→ `BLENDER_PATH` を設定するか、`PATH` に `/Applications/Blender.app/Contents/MacOS` を追加してください

**Blender が headless で落ちる**
→ まず単体で切り分けてください

```bash
blender --background --python-expr "print('headless ok')"
```

これでも落ちる場合、`smiles2fbx` ではなく Blender 本体の headless 起動が壊れています。
安定運用を優先するなら Blender LTS を別途入れて `BLENDER_PATH` で明示するのが安全です。

```bash
BLENDER_PATH="/Applications/Blender 4.5 LTS.app/Contents/MacOS/Blender" \
  bash smiles2fbx.sh "CCO" ethanol.fbx
```

LTS 配布ページ:
https://www.blender.org/download/lts/

**`ModuleNotFoundError: No module named 'rdkit'`**
→ `pip install rdkit` または `conda install -c conda-forge rdkit`

**Windows で `.sh` がそのまま実行できない**
→ WSL または Git Bash から `bash smiles2fbx.sh ...` で実行してください

**Invalid SMILES エラー**
→ SMILES 文字列をクォートで囲んでいるか確認（シェルが特殊文字を解釈する場合がある）

**FBX が Unity で真っ白**
→ Blender の PBR マテリアルは Unity の Standard/URP シェーダーに自動マッピングされない場合がある。lilToon に差し替えて Base Color を再設定してください
