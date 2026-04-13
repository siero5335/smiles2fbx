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

```bash
chmod +x smiles2fbx.sh
./smiles2fbx.sh <SMILES> <output.fbx> [options]
```

`bash` で直接呼ぶ場合:

```bash
bash smiles2fbx.sh <SMILES> <output.fbx> [options]
```

RDKit のコンフォメーション生成シードを変えたい場合:

```bash
./smiles2fbx.sh "CCO" ethanol.fbx --seed 12345
```

### 基本例

```bash
# Stickモデル（デフォルト：棒のみ、元素色CPK配色）
./smiles2fbx.sh "c1ccccc1" benzene.fbx

# 水素を省略（スッキリ＆軽量）
./smiles2fbx.sh "CCO" ethanol.fbx --no-hydrogen

# Ball-and-Stick モデル
./smiles2fbx.sh "CCO" ethanol.fbx --mode ball-and-stick
```

### モノクローム出力（アクセサリ向け）

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

### 見た目の調整

```bash
# 棒を太くする
./smiles2fbx.sh "CCO" ethanol.fbx --radius 0.10

# VRChat向けにスケール縮小
./smiles2fbx.sh "CCO" ethanol.fbx --scale 0.3

# ポリゴンをさらに削減（segments=6）
./smiles2fbx.sh "CCO" ethanol.fbx --segments 6
```

## オプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| `--segments N` | `8` | シリンダー/球の分割数。低いほど軽量 |
| `--scale F` | `1.0` | 全体スケール |
| `--radius F` | `0.06` | 棒の太さ |
| `--mode MODE` | `stick` | `stick`（棒のみ）または `ball-and-stick` |
| `--seed N` | `61453` | RDKit の 3D コンフォメーション生成シード |
| `--no-hydrogen` | *(表示)* | 水素原子と結合を非表示 |
| `--mono [HEX]` | *(CPK配色)* | モノクローム出力。HEX省略時はシルバー `C0C0C0` |
| `--metallic F` | `0.1` / mono時 `0.9` | PBR Metallic 値（0.0〜1.0） |
| `--roughness F` | `0.4` / mono時 `0.15` | PBR Roughness 値（0.0〜1.0） |

## ファイル構成

```
smiles2fbx/
├── smiles2fbx.sh     # エントリポイント（シェルスクリプト）
├── mol_to_fbx.py     # Blender Python スクリプト（molecule JSON→FBX）
└── README.md
```

## 処理フロー

```
SMILES  ──(RDKit)──▶  molecule JSON  ──(Blender headless)──▶  FBX
                      3D座標生成         bpyでメッシュ構築
                      力場最適化         マテリアル設定
                      結合情報生成       FBXエクスポート
```

## VRChat 向けメモ

- **Stickモデル推奨** — ボールなしでポリゴン数が大幅に少ない
- **`--no-hydrogen`** で水素を消すとさらに軽量化
- **`--segments 6`** まで下げても見た目は十分
- CPK配色（デフォルト）では棒が中点で分割され、各半分が原子の元素色で着色される
- 芳香族結合は見た目簡略化のため単結合相当の棒として出力される
- モノクローム時は分割なし（1ボンド=1シリンダー）でさらに軽量
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
