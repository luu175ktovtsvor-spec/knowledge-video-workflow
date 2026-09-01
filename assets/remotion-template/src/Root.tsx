import "./index.css";
import {Composition} from "remotion";
import {CollageKnowledgeVideo} from "./CollageKnowledgeVideo";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="CollageKnowledgeStarter16x9"
    component={CollageKnowledgeVideo}
    durationInFrames={510}
    fps={30}
    width={1920}
    height={1080}
  />
);
