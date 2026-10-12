Approved v4 video artwork

The masthead and closing card were extracted from the user's approved
Woods_Run_Digest_Oct_11_Revised_Preview_v4.mp4
approved by the publication owner.
The forester is the supplied Forester_Leonardo_Pencil_Sketch.png
supplied by the publication owner.
These assets are used only by render_daily_reel.py. The forester appears only
on the opening. Story art comes from each article's supplied image when present;
otherwise the renderer draws subject-specific editorial illustrations.

Timing: 38 opening frames + five 105-frame stories + 60 closing frames at
15 fps = 623 frames / 41.533333 seconds, matching v4's frame quantization.
The video is silent, H.264/yuv420p, 1080x1920, with faststart enabled.

Local correction mode (does not publish):
python scripts/render_daily_reel.py --source-root /path/to/canonical/dist \
  --date 2026-10-12 --output /path/to/corrected.mp4 --frames-dir /path/to/frames

Running without arguments preserves the existing daily preparation interface.
Do not dispatch prepare-assets.yml merely to preview a correction: its completed
workflow queues Buffer through the existing production handoff.
