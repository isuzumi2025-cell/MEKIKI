import "./index.css";
import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { SubjectPanelDemo } from "./SubjectPanelDemo";
import { VideoEditorDemo } from "./VideoEditorDemo";
import { FlowForgeStudioDemo } from "./FlowForgeStudioDemo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="MyComp"
        component={MyComposition}
        durationInFrames={60}
        fps={30}
        width={1280}
        height={720}
      />
      <Composition
        id="SubjectPanel"
        component={SubjectPanelDemo}
        durationInFrames={300}
        fps={30}
        width={1280}
        height={720}
      />
      <Composition
        id="VideoEditor"
        component={VideoEditorDemo}
        durationInFrames={900}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="FlowForgeStudio"
        component={FlowForgeStudioDemo}
        durationInFrames={900}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
