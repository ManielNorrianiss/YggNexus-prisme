-- seo_intro_coding_video.sql
-- Intros SEO (texte) pour les 2 nouvelles categories. A coller dans le SQL Editor WEB Supabase.
-- Apres : revalider via  python revalidate_paths.py /categories/ai-coding /categories/ai-video /categories

UPDATE categories SET seo_intro_md =
'AI coding tools help developers write, complete, refactor and debug code faster. This category covers AI pair programmers and in-editor assistants like GitHub Copilot, autonomous coding agents such as Devin, and AI-native editors and IDEs including Cursor, Windsurf and Replit. Whether you want inline code completion, a chat assistant that understands your whole repository, or an agent that ships entire features on its own, compare the leading AI coding tools by capability, workflow fit and pricing to find the right one for your stack.'
WHERE slug = 'ai-coding';

UPDATE categories SET seo_intro_md =
'AI video tools turn text prompts, images and scripts into finished video. This category spans text-to-video generators like Runway, Luma Dream Machine, Kling, Pika and Hailuo, AI avatar and spokesperson platforms such as Synthesia, HeyGen and D-ID, and editing or repurposing tools like InVideo, CapCut and Opus Clip that cut long footage into short, social-ready clips. Compare the best AI video generators and editors by output quality, length limits, avatar realism and pricing to match your creative workflow.'
WHERE slug = 'ai-video';
