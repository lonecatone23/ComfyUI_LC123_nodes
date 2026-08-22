# LC Prompt Builder — editable lists

All dropdowns and detailed preset text load from this folder at ComfyUI startup.

## Edit safely
1. Stop ComfyUI (or expect a restart after edits).
2. Edit the JSON with UTF-8 encoding.
3. Keep valid JSON (commas, quotes).
4. Restart ComfyUI so nodes pick up changes.

## Files
| File | Used by |
|------|---------|
| poses.json | LC Subject |
| actions.json | LC Subject |
| outfits.json | LC Subject (use Female/... and Male/... prefixes) |
| scene_presets.json | LC Scene Builder (name → long prompt) |
| style_presets.json | LC Style Selector |
| style_categories.json | LC Style Selector |
| quality_levels.json / quality_detail.json | LC Style Selector |
| camera_angles.json / camera_angle_detail.json | LC Camera |
| distances.json / camera_distance_detail.json | LC Camera |
| f_stops.json / depth_presets.json | LC Camera |
| lighting_styles.json / lighting_detail.json | LC Lighting |
| lighting_directions.json / light_direction_detail.json | LC Lighting |
| palette_presets.json | LC Color Palette |
| time_of_day.json / time_detail.json | LC Scene Builder |
| weather.json / weather_detail.json | LC Scene Builder |
| position_*.json | LC Subject placement |

## Notes
- List files are JSON arrays of strings.
- Detail/preset files are JSON objects: { "label": "long descriptive text" }.
- If a file is missing or invalid, built-in fallbacks are used.
- Reference thumbs (later): thumbs/scene|camera|lighting|style/<id>.webp
