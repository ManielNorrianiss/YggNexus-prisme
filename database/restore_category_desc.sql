-- Restaure les description_md courts des categories (ecrases par le 1er run B6)
update categories set description_md = 'Tools that generate and edit text with AI.' where slug = 'ai-writing';
update categories set description_md = 'No-code/low-code automation platforms.' where slug = 'automation';
update categories set description_md = 'Generate and edit images with AI.' where slug = 'ai-images';
update categories set description_md = 'Generate voice, speech and music with AI (text-to-speech, voice cloning, audio).' where slug = 'ai-audio';
update categories set description_md = 'Collect, enrich and structure data.' where slug = 'data-scraping';
update categories set description_md = 'Workspaces and tools to organize work and collaborate.' where slug = 'productivity';
update categories set description_md = 'Build apps and workflows without writing code.' where slug = 'no-code';
