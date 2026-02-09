---
description: "强制要求 LaTeX 项目遵循模块化结构，禁止在 main.tex 中直接编写长篇正文内容。"
globs: ["main.tex", "**/*.tex"]
alwaysApply: true
---

<latex_modular_structure_enforcement>
  <core_principle>
    <title>逻辑与内容分离的模块化原则</title>
    <description>
      你是一个专业的 LaTeX 排版助手。在处理本项目时，必须严格遵守"逻辑与内容分离"的模块化原则。
      禁止将长篇大论的正文直接写入 main.tex。
    </description>
  </core_principle>

  <main_tex_role>
    <title>main.tex 的职能定位</title>
    
    <allowed_content>
      <item>导言区（Preamble）：宏包加载、全局设置、自定义命令</item>
      <item>文档骨架结构：\begin{document}、\maketitle、\tableofcontents</item>
      <item>章节引用命令：\include{sections/文件名} 或 \input{sections/文件名}</item>
      <item>文档结束标记：\end{document}</item>
    </allowed_content>
    
    <requirement>
      正文部分的引入必须通过 \include{sections/文件名} 或 \input{sections/文件名} 命令完成。
      所有具体的章节内容必须存放在 sections/ 文件夹的独立子文件中。
    </requirement>
  </main_tex_role>

  <content_management_rules>
    <title>内容增删改规范</title>
    
    <add_content>
      <rule>当需要添加新内容时，必须定位到 sections/ 文件夹下对应的子文件进行操作</rule>
      <rule>如需创建新章节，必须先创建新的 .tex 文件（例如 sections/new_topic.tex）</rule>
      <rule>在 main.tex 的适当位置添加对应的引用命令（如 \include{sections/new_topic}）</rule>
      <rule>将section添加到main.tex中石，不能修改原本main.tex设定好的模板，不能修改原有的标题</rule>

    </add_content>
    
    <modify_content>
      <rule>修改现有章节内容时，必须直接编辑 sections/ 下的对应子文件</rule>
      <rule>不得将子文件内容复制到 main.tex 中进行编辑</rule>
    </modify_content>
    
    <expand_content>
      <rule>扩展章节时，在对应的 sections/*.tex 文件中添加内容</rule>
      <rule>如果内容过长，考虑进一步拆分为子章节文件</rule>
    </expand_content>
  </content_management_rules>

  <prohibited_behaviors>
    <title>严禁行为</title>
    
    <prohibition priority="critical">
      严禁在 main.tex 的 \begin{document} 之后直接插入超过 5 行以上的描述性文字或段落
    </prohibition>
    
    <prohibition priority="critical">
      严禁破坏已有的模块化结构，将子文件内容"合并"回主文件
    </prohibition>
    
    <prohibition priority="high">
      严禁在 main.tex 中直接编写章节正文，即使内容较短也应放在独立文件中
    </prohibition>
    
    <prohibition priority="high">
      严禁创建不在 sections/ 文件夹中的章节内容文件
    </prohibition>
  </prohibited_behaviors>

  <workflow_examples>
    <title>标准工作流示例</title>
    
    <example>
      <scenario>用户要求添加"敏感性分析"章节</scenario>
      <correct_approach>
        <step>1. 创建文件 sections/sensitivity_analysis.tex</step>
        <step>2. 在该文件中编写具体内容</step>
        <step>3. 在 main.tex 的适当位置添加 \include{sections/sensitivity_analysis}</step>
      </correct_approach>
      <wrong_approach>
        <step>❌ 直接在 main.tex 的 \begin{document} 后编写敏感性分析内容</step>
      </wrong_approach>
    </example>
    
    <example>
      <scenario>用户要求修改引言部分</scenario>
      <correct_approach>
        <step>1. 定位到 sections/introduction.tex 文件</step>
        <step>2. 在该文件中进行修改</step>
      </correct_approach>
      <wrong_approach>
        <step>❌ 在 main.tex 中查找 \include{sections/introduction} 并在其后直接添加内容</step>
      </wrong_approach>
    </example>
  </workflow_examples>

  <rationale>
    <title>为什么要这样做（逻辑依据）</title>
    
    <reason category="maintainability">
      <name>可维护性</name>
      <explanation>
        保持 main.tex 清洁，可以让读者一眼看清整个文档的逻辑结构，而非淹没在代码海中。
        每个章节独立管理，便于定位和修改。
      </explanation>
    </reason>
    
    <reason category="efficiency">
      <name>编译效率</name>
      <explanation>
        模块化结构允许使用 \includeonly 进行局部编译，加快预览速度。
        在修改单个章节时，可以只编译该章节，大幅提升开发效率。
      </explanation>
    </reason>
    
    <reason category="collaboration">
      <name>协作标准</name>
      <explanation>
        这是学术界处理长文档的标准工作流，符合专业规范。
        多人协作时，不同成员可以同时编辑不同的章节文件，减少冲突。
      </explanation>
    </reason>
    
    <reason category="version_control">
      <name>版本控制友好</name>
      <explanation>
        Git 等版本控制系统可以更精确地追踪每个章节的变更历史。
        回滚或比较修改时，可以针对特定章节进行操作。
      </explanation>
    </reason>
  </rationale>

  <enforcement_checklist>
    <title>执行检查清单</title>
    
    <check>在编辑任何内容前，确认操作目标是 sections/*.tex 文件，而非 main.tex</check>
    <check>添加新章节时，先创建独立的 .tex 文件，再添加引用命令</check>
    <check>修改完成后，验证 main.tex 中 \begin{document} 后没有超过 5 行的正文内容</check>
    <check>确保所有章节内容都通过 \include 或 \input 引入</check>
  </enforcement_checklist>

  <directory_structure>
    <title>标准目录结构</title>
    <structure>
      项目根目录/
      ├── main.tex              # 仅包含导言区和章节引用
      ├── sections/             # 所有章节内容存放于此
      │   ├── abstract.tex      # 摘要
      │   ├── introduction.tex  # 引言
      │   ├── assumptions.tex   # 假设
      │   ├── model.tex         # 模型建立
      │   ├── solution.tex      # 模型求解
      │   ├── results.tex       # 结果分析
      │   ├── sensitivity.tex   # 敏感性分析
      │   ├── strengths.tex     # 优缺点分析
      │   └── conclusion.tex    # 结论
      ├── figures/              # 图片文件
      ├── code/                 # 代码文件
      └── references.bib        # 参考文献
    </structure>
  </directory_structure>
</latex_modular_structure_enforcement>
