#!/bin/bash
# Cuts the raw phone clips into short, pre-sped 1080p30 segments for Remotion.
# Usage: ./cut.sh /path/to/folder/with/IMG_xxxx.MOV
set -euo pipefail
SRC="${1:?folder with the raw IMG_*.MOV clips}"
OUT="$(cd "$(dirname "$0")" && pwd)/public"
mkdir -p "$OUT"

HOUSE=IMG_3888 FLOWER=IMG_3896 TTT=IMG_3895 GD_A=IMG_3891 GD_B=IMG_5239 CHEETO=IMG_3887
# IMG_5239 was recorded landscape but tagged portrait, and is HLG. Ignore the
# rotation tag, and crop the top so bystanders behind the laptop are out of frame.
GD_B_CROP="crop=1574:885:104:195,"
# Tight crop on the gripper and keypad in IMG_5239, for the close-up of it pressing the key.
KEY_CROP="crop=720:405:1090:338,"

# cut NAME CLIP START DURATION SPEED [SIZE] [PREFILTER]
cut() {
  local name=$1 clip=$2 ss=$3 dur=$4 speed=$5 size=${6:-1920:1080} pre=${7:-}
  local rot=""
  [ "$clip" = "$GD_B" ] && rot="-display_rotation 0"
  ffmpeg -v error -y $rot -ss "$ss" -t "$dur" -i "$SRC/$clip.MOV" \
    -vf "${pre}setpts=PTS/${speed},fps=30,scale=${size},format=yuv420p" \
    -an -c:v libx264 -preset veryfast -crf 19 -g 30 \
    -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
    -metadata:s:v:0 rotate=0 -movflags +faststart "$OUT/$name.mp4"
  echo "$name"
}

# Cold open
cut o1 $HOUSE 28 3 2
cut o2 $GD_B 44.5 1.5 1 1920:1080 "$GD_B_CROP"
cut o3 $TTT 44 4.5 3
cut o4 $CHEETO 17.6 3 2
# Opening montage, after the four fast cuts
cut oa $GD_A 75.2 2.5 1
cut ob $HOUSE 38 13.5 6
cut oc $TTT 12 13.5 6
cut od $GD_B 20 2.5 1 1920:1080 "$KEY_CROP"
cut oe $CHEETO 8.4 1.4 0.6
cut of $FLOWER 46 20.5 9
# Drawing
cut d1 $HOUSE 14 36.8 2.4
cut d2 $HOUSE 50 3.8 1
cut d3 $FLOWER 24 42.5 14
cut d4 $FLOWER 70.3 2.3 1
# Tic-tac-toe
cut t1 $TTT 8 23 8
cut t2 $TTT 33 5.7 1.5
cut t3 $TTT 39 11.6 4
cut t4 $TTT 51 5.4 2.5
cut t5 $TTT 57 6.6 4
cut t6 $TTT 63.5 2.9 2.5
cut t7 $TTT 66.5 14.4 6
cut t8 $TTT 81.3 3.4 1
# Geometry Dash. g1+g2 are one attempt (0% to 40%); g3+g4 are the full clear (40% to 100%).
cut g1 $GD_A 3.6 4.6 1
cut g2 $GD_A 8 32.3 8
# IMG_5239 starts with the phone being turned; skip that first second.
cut gk $GD_B 2.0 2.5 1 1920:1080 "$KEY_CROP"
cut g3 $GD_B 4.4 36 10 1920:1080 "$GD_B_CROP"
cut g4a $GD_B 40 8.2 4 1920:1080 "$GD_B_CROP"
cut g4 $GD_B 48 3.6 1 1920:1080 "$GD_B_CROP"
# The clip ends a quarter second after 100%, so the last frame is held under the "100%" title.
ffmpeg -v error -y -sseof -0.12 -i "$OUT/g4.mp4" -frames:v 1 -update 1 -q:v 2 "$OUT/g_end.jpg"
# Feeding
cut f1 $CHEETO 9 17.1 1.4
# Close: six small tiles and the arm at rest over a blank page
cut gr1 $HOUSE 18 33 4 960:540
cut gr2 $FLOWER 30 41 5 960:540
cut gr3 $TTT 40 41 5 960:540
cut gr4 $GD_A 8 33 4 960:540
cut gr5 $GD_B 18.5 33 4 960:540 "$GD_B_CROP"
cut gr6 $CHEETO 9 16.5 2 960:540
cut rest $FLOWER 12.3 1.45 0.14
echo "all segments written to $OUT"
