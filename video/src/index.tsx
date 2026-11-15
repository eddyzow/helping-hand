import React from "react";
import { Composition, registerRoot } from "remotion";
import { Demo, T } from "./Demo";

function Root() {
  return <Composition id="Demo" component={Demo} durationInFrames={T.end} fps={30} width={1920} height={1080} />;
}

registerRoot(Root);
