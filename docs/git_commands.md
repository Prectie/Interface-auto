# 当前项目 Git 常用命令

本文档只写当前 AutoAPI 项目里最常用、最实用的 Git 命令。

## 1. 查看当前改了什么

```bash
git status --short
```

作用：

- 查看哪些文件被修改。
- 查看哪些文件是新增未跟踪文件。
- 查看哪些文件被删除。

常见输出：

```text
 M run.py
?? docs/git_commands.md
 D old_file.py
```

含义：

- `M`：文件已修改。
- `??`：新文件，Git 还没有跟踪。
- `D`：文件被删除。

## 2. 查看某个文件具体改了什么

```bash
git diff -- run.py
```

作用：

- 查看 `run.py` 当前工作区相对 Git 版本的差异。
- 这是你检查“覆盖前后有什么区别”的核心命令。

也可以查看多个文件：

```bash
git diff -- run.py Core/repository.py
```

## 3. 查看所有已修改文件的差异

```bash
git diff
```

作用：

- 查看所有已跟踪文件的详细改动。
- 不包含 `??` 新文件的内容。

## 4. 查看改动统计

```bash
git diff --stat
```

作用：

- 不看具体代码，只看哪些文件改了多少行。
- 适合快速判断改动范围是否过大。

## 5. 暂存某个文件

```bash
git add run.py
```

作用：

- 把 `run.py` 放进下一次 commit。
- 只是暂存，不等于提交。

暂存多个文件：

```bash
git add run.py Core/repository.py Schema/data_models.py
```

## 6. 暂存当前目录所有改动

```bash
git add .
```

作用：

- 把当前目录下所有新增、修改、删除都放进下一次 commit。

注意：

- 当前项目有一些无关脏文件时，不建议直接用 `git add .`。
- 更推荐一个一个文件确认后再 `git add <file>`。

## 7. 查看已经暂存的差异

```bash
git diff --cached
```

作用：

- 查看已经 `git add`、准备提交的内容。
- commit 前建议看一遍。

## 8. 提交改动

```bash
git commit -m "docs: add AutoAPI planning docs"
```

作用：

- 把暂存区里的改动提交到 Git 历史。

提交信息建议：

```text
docs: add git command guide
feat: add p0 data models
refactor: load p0 yaml assets
test: update repository tests
```

## 9. 查看提交历史

```bash
git log --oneline -5
```

作用：

- 查看最近 5 次提交。
- 每条提交只显示一行。

## 10. 查看某次提交改了什么

```bash
git show <commit_id>
```

作用：

- 查看某个 commit 的详细改动。

示例：

```bash
git show abc1234
```

## 11. 只看某次提交的文件统计

```bash
git show --stat <commit_id>
```

作用：

- 查看某次提交改了哪些文件、每个文件改了多少行。

## 12. 放弃某个文件的未暂存改动

```bash
git restore run.py
```

作用：

- 把 `run.py` 恢复到最近一次 commit 的状态。

注意：

- 这个命令会丢弃当前文件的未提交改动。
- 使用前先执行：

```bash
git diff -- run.py
```

确认不要这些改动后再执行。

## 13. 取消暂存某个文件

```bash
git restore --staged run.py
```

作用：

- 把 `run.py` 从暂存区拿出来。
- 不会丢失文件内容改动。

## 14. 查看某个文件属于谁改过

```bash
git blame run.py
```

作用：

- 查看 `run.py` 每一行最后是谁在哪次 commit 改的。
- 排查历史原因时有用。

## 15. 当前项目最推荐的日常流程

1. 查看状态：

```bash
git status --short
```

2. 查看具体差异：

```bash
git diff -- <file>
```

3. 暂存确认过的文件：

```bash
git add <file>
```

4. 查看准备提交的内容：

```bash
git diff --cached
```

5. 提交：

```bash
git commit -m "type: message"
```

