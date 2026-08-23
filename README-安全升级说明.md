# 南风H3 V8.1 安全升级包

1. 确认ComfyUI没有运行任务并完全退出。
2. 将本包的 `nanfeng_prompt_nodes` 覆盖到 `ComfyUI/custom_nodes/nanfeng_prompt_nodes`。
3. 本包不含 `.env`，不会覆盖已有API配置；首次安装请复制 `.env.example` 为 `.env`。
4. 重启ComfyUI并用 Ctrl+F5 强制刷新。

包含V8.1智能分镜、独立自然语言创意保存、素材换图/删除/换位、30 MiB单图限制、连续Sigma轨迹及同LoRA一二采。
不包含模型、媒体、API密钥、视觉缓存或测试缓存。
