
## 问题
目前oral english使用的voice llm智能程度较低，无法较好的follow长的复杂的prompt，能接受的prompt长度也非常受限，导致一直卡在重复知识点上

## 解决方案

每次建立会话的时候，请使用general llm来生成给voice llm需要执行的当前课程需要的知识点、学生的简介，尽量简洁，也无须包含全局细节, 这样保障整体的教学目标仍然处于general llm的掌控之下
