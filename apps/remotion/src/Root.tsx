import "./index.css";
import { Composition } from "remotion";
import { SourceHarborFrontDoor } from "./SourceHarborFrontDoor";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="SourceHarborFrontDoor"
        component={SourceHarborFrontDoor}
        durationInFrames={480}
        fps={30}
        width={1280}
        height={720}
        defaultProps={{
          title: "Start with one finished reading surface",
          subtitle:
            "Then inspect proof, search, and builder tools only when the reading path asks for them.",
        }}
      />
    </>
  );
};
