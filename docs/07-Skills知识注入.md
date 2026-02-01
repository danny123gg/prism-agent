# 07 - Skills 知识注入

> 配套代码：`src/v6_skills.py`
>
> **目标**：学会使用 Skills 机制，让 Agent 成为领域专家

---

## 通用 vs 专业

通用的 Agent 什么都能聊，但什么都不精通。

你让它审查代码，它可以给你一些泛泛的建议——"代码结构不够清晰"、"建议添加注释"。但它不会知道：

- 你们团队的代码规范是什么
- 哪些模式是推荐的，哪些要避免
- 这个项目踩过哪些坑
- 输出应该用什么格式

Skills 解决的就是这个问题。

你可以把领域知识写成一个文档，Agent 会在需要的时候调用这个"技能"，按照你定义的方式工作。

**Skills 是"给 Agent 加知识"。它让通用的 Agent 变得专业。**

---

## Skills 的结构

Skills 是放在 `.claude/skills/` 目录下的 Markdown 文件：

```
.claude/
└── skills/
    └── code-reviewer/
        └── SKILL.md
```

每个技能一个目录，目录名就是技能名。

---

## SKILL.md 的格式

```markdown
---
name: code-reviewer
description: "Use this skill when reviewing Python code for quality and best practices."
allowed-tools: Read, Glob, Grep
---

# Code Reviewer Skill

## When to Use This Skill
- Review Python code for quality issues
- Find potential bugs or security vulnerabilities
- Check code style and best practices

## Review Process

### 1. Initial Assessment
First, understand the code's purpose...

### 2. Check Categories
#### Code Quality
- [ ] Clear variable names
- [ ] Appropriate function length (< 50 lines)
- [ ] Single responsibility principle

#### Potential Bugs
- [ ] Error handling
- [ ] Edge cases
- [ ] Resource cleanup

## Output Format

Structure your review as:

## Code Review: [filename]

### Summary
[1-2 sentence overview]

### Critical Issues
[!] Issue description...

### Improvements
[?] Suggestion...

### Positive Aspects
[+] Good practice observed...
```

### YAML Frontmatter

| 属性 | 说明 |
|------|------|
| `name` | 技能唯一标识（kebab-case） |
| `description` | Agent 决定是否使用的依据 |
| `allowed-tools` | 此技能可使用的工具 |

### Markdown 正文

正文就是你要注入的知识：

- 什么时候使用这个技能
- 具体的工作流程
- 检查清单
- 输出格式模板
- 最佳实践

Agent 会读取这些内容，并按照你的要求工作。

---

## 配置 Agent 使用 Skills

```python
options = ClaudeAgentOptions(
    model="sonnet",
    permission_mode="bypassPermissions",
    setting_sources=["project"],  # 关键：从项目加载技能
    allowed_tools=["Skill", "Read", "Glob", "Grep"],  # 必须包含 Skill
    system_prompt="When reviewing code, use the 'code-reviewer' skill.",
)
```

关键配置：

- `setting_sources=["project"]` — 从 `.claude/skills/` 加载技能
- `allowed_tools` 必须包含 `"Skill"` — 允许 Agent 调用技能

---

## 对比效果

### 没有 Skill

```
### Strengths
1. Clear documentation...
2. Good structure...

### Suggestions for Improvement
1. Type checking via string comparison...
```

输出格式随意，检查项不确定，质量取决于 Agent 的"心情"。

### 使用 Skill

```
## Code Review: src/v0_hello.py

### Summary
这是一个 Claude Agent SDK 的最小示例代码...

### Critical Issues
无严重问题。

### Improvements
**[?] 缺少类型注解** (第 19 行)
建议添加函数参数和返回值的类型注解...

### Minor Issues
**[i] `permission_mode` 使用魔法字符串** (第 23 行)
考虑使用枚举或常量...

### Positive Aspects
**[+] 优秀的文件头文档**
文件开头有清晰的说明...
```

输出格式统一，使用了定义的严重级别标记，有结构化的检查清单。

---

## 运行示例

```bash
python src/v6_skills.py
```

你会看到有技能和无技能的对比输出。

---

## 创建自己的 Skill

### 步骤 1：创建目录

```bash
mkdir -p .claude/skills/my-skill
```

### 步骤 2：编写 SKILL.md

```markdown
---
name: my-skill
description: "Use this skill when..."
allowed-tools: Read, Write
---

# My Skill

## When to Use
描述使用场景...

## Process
1. 第一步...
2. 第二步...

## Output Format
定义输出格式...

## Best Practices
- 最佳实践 1...
- 最佳实践 2...
```

### 步骤 3：配置 Agent

```python
options = ClaudeAgentOptions(
    setting_sources=["project"],
    allowed_tools=["Skill", ...],
    system_prompt="Use 'my-skill' when...",
)
```

---

## Skills vs System Prompt

| 方面 | System Prompt | Skills |
|------|---------------|--------|
| 长度 | 受 token 限制 | 可以很长 |
| 组织 | 单一文本块 | 结构化 Markdown |
| 复用 | 每次配置 | 文件级复用 |
| 加载 | 总是加载 | Agent 决定是否调用 |
| 适用 | 通用指令 | 领域专业知识 |

**建议**：

- System Prompt 用于基本行为指令
- Skills 用于详细的领域知识

两者可以配合使用。

---

## 一些问题

**Q: Agent 怎么决定是否使用 Skill？**

根据 Skill 的 `description` 和用户的请求来判断。确保 description 清晰描述使用场景。

**Q: 可以有多个 Skills 吗？**

可以。每个 Skill 放在独立目录：

```
.claude/skills/
├── code-reviewer/
│   └── SKILL.md
├── doc-writer/
│   └── SKILL.md
└── test-generator/
    └── SKILL.md
```

Agent 会根据任务选择合适的 Skill。

**Q: Skill 可以调用其他 Skill 吗？**

不直接支持。但 Agent 可以在一次对话中使用多个 Skills。

---

## 小结

Skills 是给 Agent 注入领域知识的机制。

通过 Skills，你可以：

- 定义专业的工作流程
- 统一输出格式
- 嵌入最佳实践
- 让 Agent 了解你的特定需求

这是从"通用助手"到"领域专家"的关键一步。

---

## 下一步

在 [08-MCP扩展能力](./08-MCP扩展能力.md) 中，我们会学习如何通过 MCP 连接外部服务，让 Agent 获得更多能力。

这是最后一个版本，也是能力边界的扩展。
