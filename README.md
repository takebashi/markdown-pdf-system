# Markdown to PDF

Markdownファイルを、デザイン済みの読みやすいPDFへ変換するツールです。

Repository slug: `md2pdf`

## Web App

GitHub Pagesで動くブラウザ版を `docs/` に追加しています。

- Markdownを貼り付ける、または `.md` ファイルを開く
- テーマと密度を選ぶ
- プレビューを確認する
- `PDF` ボタンからブラウザの印刷機能でPDF保存する

公開URL:

```text
https://takebashi.github.io/md2pdf/
```

## CLI

Python版CLIも引き続き使えます。

```powershell
python .\md2pdf.py .\sample.md .\sample.pdf --preview-dir .\preview
```

テーマを変える場合:

```powershell
python .\md2pdf.py .\sample.md .\sample_editorial.pdf --theme editorial --preview-dir .\preview
```

## 入力Markdownで使えるもの

- YAML風の先頭メタ情報: `title`, `subtitle`, `author`, `date`
- 見出し: `#` から `####`
- 段落
- 太字、斜体、インラインコード、リンク
- 箇条書き、番号付きリスト
- 引用
- fenced code block
- Markdown表
- ローカル画像: `![説明](path/to/image.png)`

## CLIに必要なもの

- Python 3.10以降
- `reportlab`
- 任意: `pdftoppm`

```powershell
pip install reportlab
```

PNGプレビューも作る場合はPopplerを入れて、`pdftoppm` にPATHを通します。

## 設計方針

ChatGPTに毎回PDFデザインまで考えさせるのではなく、PDFの見た目はテンプレートに固定します。ChatGPTにはMarkdown原稿の整理だけを任せ、このツールで即座にPDF化する想定です。
