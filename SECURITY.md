# Security

Never commit `.env`, API keys, visual-analysis caches, local media, or model weights.

V8.1 keeps provider credentials server-side in `nanfeng_prompt_nodes/.env`; workflow JSON and frontend configuration responses do not expose key values. Use `.env.example` as the template.
