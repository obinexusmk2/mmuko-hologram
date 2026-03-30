MMUKO Holographic Interface — Tree Sprite Assets
================================================

Place your AnimatedTreeFree sprites in this folder.

Expected filenames (HTML canvas will look for these):

  tree_row.png   — sprite-sheet with 14 frames in a single horizontal row
                   (this is the animated tree row from AnimatedTreeFree)
                   Size: any — the canvas will scale it automatically

  tree.png       — single foreground tree sprite (optional fallback)
  tree_bg.png    — single background tree sprite (optional fallback)

Source:  C:\Users\OBINexus\Downloads\AnimatedTreeFree
Copy:    xcopy /E /Y "C:\Users\OBINexus\Downloads\AnimatedTreeFree\*" "static\assets\trees\"

If no sprite files are present the canvas draws procedural autumn trees
using the same colour palette — the parallax will still work correctly.
