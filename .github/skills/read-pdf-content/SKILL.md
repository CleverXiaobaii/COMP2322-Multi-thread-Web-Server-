# Skill: Read PDF And Save Content

## Purpose

读取 PDF 文件内容，并将提取文本保存到指定文件，便于后续检索、分析或版本管理。

## When To Use

- 用户要求“读取 PDF 内容并保存”。
- 需要把 PDF 文本输出为 `.txt`/`.md` 文件。
- 需要对仓库中的 PDF 进行可追踪的文本归档。

## Inputs

- `pdf_path`: PDF 文件路径（必填）。
- `output_path`: 输出文本路径（必填）。

## Output

- 在 `output_path` 生成 UTF-8 文本文件。
- 控制台输出页数、字符数和保存路径。

## Steps

1. 安装依赖：`pip install pypdf`
2. 执行脚本：

```bash
python3 tools/read_pdf_and_save.py --pdf <pdf_path> --out <output_path>
```

3. 检查输出文件是否生成，并抽样核对内容。

## Example

```bash
python3 tools/read_pdf_and_save.py --pdf Project.pdf --out output/project_extracted.txt
```

## Notes

- 扫描版 PDF（纯图片）可能提取不到文本，需要 OCR 工具。
- 页面中公式/表格的排版可能与原文不同。
