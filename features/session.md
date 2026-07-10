
# Background
因为学生切换session导致状态丢失，我想重构下交互模型

# Goal
1. 考虑到教育是一对一的，这样请以course的维度来记录session，每个学科/course一个session，例如{course}_session.log，这样学生的会话记录不会因为切换而丢失; 现有的session也请迁移到新的、统一的session文件
2. 考虑到context有限，系统最多加载最近20轮次会话，超过20轮次的会话请压缩到{course}_mem.log, 请按照session来压缩，重点记录学生的状态和相关的知识点、变化, 并且把压缩的context也作为model context
3. 目前学生较小，不知道怎么用，Agent需要主动，每次识别到新session，请系统主动代替给Agent发一些“学生checkin”的消息，这样学生一打开系统，能看到接下来的课堂计划

# Arch
1. 使用sqlite记录session_id以及是否变化
2. 压缩会话请使用离线天级任务, 每天运行一次即可
