import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const COLORS = {
  coral: "#ef5848",
  deep: "#083746",
  green: "#74d38b",
  ink: "#171717",
  paper: "#fff8e7",
  teal: "#177f91",
  yellow: "#ffd25a",
};

export const LAYER = {
  stage: 0,
  rear: 10,
  subjectBack: 20,
  occluder: 30,
  subjectFront: 40,
  graphic: 50,
  keyword: 60,
  chapter: 70,
  // Semantic layer name, not a CSS transition.
  // eslint-disable-next-line @remotion/non-pure-animation
  transition: 90,
  titleCard: 100,
  caption: 110,
} as const;

export type LayerName = keyof typeof LAYER;

const HOUSE = "media/house-components";
const ASSETS = {
  backgrounds: {
    serviceShop: `${HOUSE}/backgrounds/service-shop.png`,
    warehouseOffice: `${HOUSE}/backgrounds/warehouse-office.png`,
  },
  characters: {
    beaverHandoff: `${HOUSE}/characters/beaver-operator/handoff-empty.png`,
    beaverLift: `${HOUSE}/characters/beaver-operator/lift-empty.png`,
    capybaraReceive: `${HOUSE}/characters/capybara-customer/receive-empty.png`,
    otterCelebrate: `${HOUSE}/characters/otter-narrator/celebrate.png`,
    otterExplain: `${HOUSE}/characters/otter-narrator/explain-right.png`,
  },
  modules: {
    serviceCounter: `${HOUSE}/modules/shop-service/service-counter.png`,
  },
  props: {
    parcel: `${HOUSE}/props/service-operations/parcel-closed.png`,
  },
};

const progress = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

type SpriteLayerProps = {
  src: string;
  x: number;
  y: number;
  width: number;
  height?: number;
  enterAt?: number;
  exitAt?: number;
  fromX?: number;
  fromY?: number;
  moveAt?: number;
  toX?: number;
  toY?: number;
  moveDuration?: number;
  layer?: LayerName;
  shadow?: boolean;
};

export const SpriteLayer: React.FC<SpriteLayerProps> = ({
  src,
  x,
  y,
  width,
  height,
  enterAt = 0,
  exitAt,
  fromX = 60,
  fromY = 0,
  moveAt,
  toX,
  toY,
  moveDuration = 24,
  layer = "subjectFront",
  shadow = true,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const entrance = spring({
    fps,
    frame: Math.max(0, frame - enterAt),
    config: {damping: 18, stiffness: 150},
  });
  const exit = exitAt === undefined ? 1 : 1 - progress(frame, exitAt, 10);
  const move = moveAt === undefined ? 0 : progress(frame, moveAt, moveDuration);
  const currentX = interpolate(move, [0, 1], [x, toX ?? x]);
  const currentY = interpolate(move, [0, 1], [y, toY ?? y]);
  const safeMargin = 60;
  const visualBottom = 860;
  const entranceX = (1 - entrance) * fromX;
  const entranceY = (1 - entrance) * fromY;
  const safeWidth = Math.min(width, 1920 - safeMargin * 2);
  const safeX = Math.max(safeMargin - entranceX, Math.min(currentX, 1920 - safeWidth - safeMargin - entranceX));
  const safeY = Math.max(40 - entranceY, Math.min(currentY, visualBottom - 80 - entranceY));
  const availableHeight = visualBottom - safeY - entranceY;
  const safeHeight = Math.max(80, Math.min(height ?? availableHeight, availableHeight));

  return (
    <div
      style={{
        position: "absolute",
        left: safeX,
        top: safeY,
        width: safeWidth,
        height: safeHeight,
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        opacity: entrance * exit,
        translate: `${entranceX}px ${entranceY}px`,
        scale: 0.9 + entrance * 0.1,
        transformOrigin: "50% 100%",
        filter: shadow ? "drop-shadow(0 20px 13px rgba(0,0,0,.25))" : undefined,
        zIndex: LAYER[layer],
      }}
    >
      <Img
        src={staticFile(src)}
        style={{width: "100%", height: "100%", objectFit: "contain", objectPosition: "50% 100%"}}
      />
    </div>
  );
};

export const PoseSwap: React.FC<{
  from: string;
  to: string;
  x: number;
  y: number;
  width: number;
  height?: number;
  swapAt: number;
  layer?: LayerName;
}> = ({from, to, x, y, width, height, swapAt, layer = "subjectFront"}) => {
  const frame = useCurrentFrame();
  const swap = progress(frame, swapAt - 5, 10);
  const safeMargin = 60;
  const safeWidth = Math.min(width, 1920 - safeMargin * 2);
  const safeX = Math.max(safeMargin, Math.min(x, 1920 - safeWidth - safeMargin));
  const safeY = Math.max(40, Math.min(y, 780));
  const availableHeight = 860 - safeY;
  const safeHeight = Math.max(80, Math.min(height ?? availableHeight, availableHeight));
  const sharedStyle: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    objectFit: "contain",
    objectPosition: "50% 100%",
    transformOrigin: "50% 100%",
  };
  return (
    <div style={{position: "absolute", left: safeX, top: safeY, width: safeWidth, height: safeHeight, filter: "drop-shadow(0 20px 13px rgba(0,0,0,.25))", zIndex: LAYER[layer]}}>
      <Img src={staticFile(from)} style={{...sharedStyle, opacity: 1 - swap}} />
      <Img src={staticFile(to)} style={{...sharedStyle, opacity: swap}} />
    </div>
  );
};

export const PropContact: React.FC<{
  src: string;
  from: {x: number; y: number};
  to: {x: number; y: number};
  width: number;
  startAt: number;
  duration: number;
}> = ({src, from, to, width, startAt, duration}) => {
  const frame = useCurrentFrame();
  const p = progress(frame, startAt, duration);
  return (
    <SpriteLayer
      src={src}
      x={interpolate(p, [0, 1], [from.x, to.x])}
      y={interpolate(p, [0, 0.5, 1], [from.y, Math.min(from.y, to.y) - 70, to.y])}
      width={width}
      enterAt={startAt}
      fromX={0}
      layer="subjectFront"
    />
  );
};

const SceneBackdrop: React.FC<{src: string}> = ({src}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{overflow: "hidden", background: COLORS.deep, zIndex: LAYER.stage}}>
      <Img
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          scale: interpolate(frame, [0, 300], [1.02, 1.055], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          filter: "blur(1.2px) saturate(.96)",
        }}
      />
      <AbsoluteFill style={{background: "radial-gradient(circle at 50% 42%, transparent 0 48%, rgba(2,22,30,.28) 100%)"}} />
    </AbsoluteFill>
  );
};

export const DiagramStage: React.FC = () => (
  <AbsoluteFill
    style={{
      overflow: "hidden",
      zIndex: LAYER.stage,
      background: "linear-gradient(180deg, #93d8cf 0%, #b8e0c5 66%, #d6c895 66%, #efe1b8 100%)",
    }}
  >
    <AbsoluteFill
      style={{
        opacity: 0.2,
        backgroundImage:
          "radial-gradient(circle at 20px 20px, rgba(8,55,70,.35) 0 3px, transparent 4px), repeating-linear-gradient(125deg, transparent 0 64px, rgba(255,255,255,.42) 65px 68px, transparent 69px 132px)",
        backgroundSize: "92px 92px, 220px 220px",
      }}
    />
    <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: 170, background: "linear-gradient(180deg, transparent, rgba(68,86,55,.24))"}} />
  </AbsoluteFill>
);

export const EvidencePanel: React.FC<{
  x: number;
  y: number;
  width: number;
  title: string;
  rows: Array<{label: string; value: string; accent?: boolean}>;
  enterAt: number;
}> = ({x, y, width, title, rows, enterAt}) => {
  const frame = useCurrentFrame();
  const p = progress(frame, enterAt, 12);
  return (
    <div style={{position: "absolute", left: x, top: y, width, padding: 30, borderRadius: 24, background: "rgba(255,248,231,.97)", border: `7px solid ${COLORS.ink}`, boxShadow: "0 24px 42px rgba(0,0,0,.24)", opacity: p, translate: `0px ${(1 - p) * 42}px`, zIndex: LAYER.graphic}}>
      <div style={{fontSize: 34, fontWeight: 950, color: COLORS.ink}}>{title}</div>
      <div style={{display: "grid", gap: 12, marginTop: 22}}>
        {rows.map((row) => (
          <div key={`${row.label}-${row.value}`} style={{display: "grid", gridTemplateColumns: "1fr 1.25fr", gap: 16, alignItems: "center", padding: "13px 16px", borderRadius: 12, background: row.accent ? "#f8cfc5" : "#e8eee7", fontSize: 26, fontWeight: 800, color: COLORS.ink}}>
            <span>{row.label}</span>
            <span>{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export const PhonePanel: React.FC<{label: string; status: string; accent: string}> = ({label, status, accent}) => (
  <div style={{width: "100%", height: "100%", borderRadius: 52, padding: 18, background: "#31464d", border: `8px solid ${COLORS.ink}`, boxShadow: "0 24px 34px rgba(0,0,0,.25)"}}>
    <div style={{height: "100%", borderRadius: 34, background: COLORS.paper, padding: 28, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center"}}>
      <div style={{fontSize: 24, fontWeight: 900, color: COLORS.teal}}>{label}</div>
      <div style={{marginTop: 24, padding: "18px 22px", borderRadius: 18, background: accent, color: COLORS.ink, fontSize: 30, fontWeight: 950}}>{status}</div>
    </div>
  </div>
);

export const StateReplace: React.FC<{
  before: React.ReactNode;
  after: React.ReactNode;
  x: number;
  y: number;
  width: number;
  height: number;
  swapAt: number;
}> = ({before, after, x, y, width, height, swapAt}) => {
  const frame = useCurrentFrame();
  const p = progress(frame, swapAt - 6, 12);
  const shared: React.CSSProperties = {position: "absolute", inset: 0};
  return (
    <div style={{position: "absolute", left: x, top: y, width, height, zIndex: LAYER.graphic}}>
      <div style={{...shared, opacity: 1 - p, translate: `${-p * 36}px 0px`}}>{before}</div>
      <div style={{...shared, opacity: p, translate: `${(1 - p) * 36}px 0px`}}>{after}</div>
    </div>
  );
};

export const ProcessFlow: React.FC<{x: number; y: number; width: number; labels: string[]; enterAt: number}> = ({x, y, width, labels, enterAt}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{position: "absolute", left: x, top: y, width, display: "flex", alignItems: "center", justifyContent: "space-between", zIndex: LAYER.graphic}}>
      {labels.map((label, index) => {
        const p = progress(frame, enterAt + index * 10, 10);
        return (
          <div key={label} style={{display: "contents"}}>
            <div style={{minWidth: 170, padding: "18px 24px", borderRadius: 18, background: COLORS.paper, border: `5px solid ${COLORS.ink}`, color: COLORS.ink, fontSize: 28, fontWeight: 950, textAlign: "center", opacity: p, scale: 0.86 + p * 0.14}}>{label}</div>
            {index < labels.length - 1 ? <div style={{height: 8, flex: 1, margin: "0 16px", borderRadius: 8, background: COLORS.coral, scale: `${p} 1`, transformOrigin: "0 50%"}} /> : null}
          </div>
        );
      })}
    </div>
  );
};

export const ThoughtBubble: React.FC<{
  x: number;
  y: number;
  width: number;
  assetSrc: string;
  enterAt: number;
}> = ({x, y, width, assetSrc, enterAt}) => {
  const frame = useCurrentFrame();
  const p = progress(frame, enterAt, 12);
  return (
    <div style={{position: "absolute", left: x, top: y, width, height: width * 0.68, borderRadius: "50%", background: "rgba(255,248,231,.96)", border: `7px solid ${COLORS.ink}`, boxShadow: "0 18px 32px rgba(0,0,0,.22)", opacity: p, scale: 0.86 + p * 0.14, zIndex: LAYER.graphic}}>
      <Img src={staticFile(assetSrc)} style={{position: "absolute", inset: "8% 17%", width: "66%", height: "84%", objectFit: "contain"}} />
      <div style={{position: "absolute", left: -34, bottom: -22, width: 42, height: 42, borderRadius: "50%", background: COLORS.paper, border: `6px solid ${COLORS.ink}`}} />
      <div style={{position: "absolute", left: -62, bottom: -50, width: 24, height: 24, borderRadius: "50%", background: COLORS.paper, border: `5px solid ${COLORS.ink}`}} />
    </div>
  );
};

export const KineticKeyword: React.FC<{text: string; x: number; y: number; enterAt: number; color?: string}> = ({text, x, y, enterAt, color = COLORS.yellow}) => {
  const frame = useCurrentFrame();
  const p = progress(frame, enterAt, 10);
  return (
    <div style={{position: "absolute", left: x, top: y, color, fontSize: 66, fontWeight: 950, WebkitTextStroke: `5px ${COLORS.ink}`, paintOrder: "stroke fill", opacity: p, scale: 0.82 + p * 0.18, zIndex: LAYER.keyword}}>
      {text}
    </div>
  );
};

export const OutlinedSubtitle: React.FC<{text: string}> = ({text}) => (
  <div style={{position: "absolute", left: 100, right: 100, bottom: 62, color: "white", fontSize: 54, fontWeight: 950, letterSpacing: ".02em", lineHeight: 1.25, textAlign: "center", WebkitTextStroke: "6px #111", paintOrder: "stroke fill", textShadow: "0 8px 16px rgba(0,0,0,.35)", zIndex: LAYER.caption}}>
    {text}
  </div>
);

export const TypewriterCard: React.FC<{text: string}> = ({text}) => {
  const frame = useCurrentFrame();
  const visible = Math.ceil(interpolate(frame, [8, 42], [0, text.length], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}));
  const pulse = Math.floor(frame / 8) % 2 === 0;
  return (
    <AbsoluteFill style={{background: "#050505", alignItems: "center", justifyContent: "center", fontFamily: "STKaiti, KaiTi, serif", zIndex: LAYER.titleCard}}>
      <Img src={staticFile(ASSETS.characters.otterExplain)} style={{position: "absolute", left: 210, bottom: -30, width: 500, opacity: 0.11, filter: "grayscale(1) brightness(.45)"}} />
      <Img src={staticFile(ASSETS.characters.capybaraReceive)} style={{position: "absolute", right: 210, bottom: -30, width: 500, opacity: 0.11, filter: "grayscale(1) brightness(.45)"}} />
      <div style={{position: "absolute", inset: 0, opacity: 0.18, background: "radial-gradient(circle at center, #b64d35 0, transparent 48%)"}} />
      <div style={{color: "#e63028", fontSize: 84, fontWeight: 900, textShadow: "0 0 18px rgba(230,48,40,.62)", letterSpacing: ".08em", zIndex: 4}}>
        {text.slice(0, visible)}
        <span style={{color: "white", opacity: pulse ? 1 : 0}}>│</span>
      </div>
    </AbsoluteFill>
  );
};

export const ForegroundWipe: React.FC<{startAt: number}> = ({startAt}) => {
  const frame = useCurrentFrame();
  const p = progress(frame, startAt, 14);
  if (p <= 0) return null;
  return <div style={{position: "absolute", left: -900, top: -180, width: 1200, height: 1450, borderRadius: "48%", background: COLORS.deep, filter: "blur(24px)", translate: `${p * 3000}px 0px`, rotate: "-8deg", zIndex: LAYER.transition}} />;
};

const ProblemScene: React.FC = () => (
  <AbsoluteFill>
    <SceneBackdrop src={ASSETS.backgrounds.warehouseOffice} />
    <SpriteLayer src={ASSETS.characters.otterExplain} x={170} y={395} width={500} enterAt={8} fromX={-80} layer="subjectBack" />
    <SpriteLayer src={ASSETS.characters.beaverLift} x={650} y={440} width={455} enterAt={28} fromX={-60} layer="subjectBack" />
    <SpriteLayer src={ASSETS.modules.serviceCounter} x={1000} y={365} width={710} enterAt={5} fromY={35} layer="occluder" />
    <PropContact src={ASSETS.props.parcel} from={{x: 1540, y: 220}} to={{x: 865, y: 560}} width={260} startAt={36} duration={48} />
    <OutlinedSubtitle text="人物、道具和结果必须在同一拍里发生关系" />
  </AbsoluteFill>
);

const DiagramScene: React.FC = () => (
  <AbsoluteFill>
    <DiagramStage />
    <SpriteLayer src={ASSETS.characters.otterExplain} x={90} y={430} width={470} enterAt={5} fromX={-70} />
    <StateReplace
      x={610}
      y={150}
      width={340}
      height={560}
      swapAt={72}
      before={<PhonePanel label="旧状态" status="无法继续" accent="#f4c6bd" />}
      after={<PhonePanel label="新状态" status="恢复可用" accent="#bee1c6" />}
    />
    <EvidencePanel
      x={1060}
      y={160}
      width={690}
      title="证据面板"
      enterAt={40}
      rows={[
        {label: "对象", value: "同一设备"},
        {label: "变化", value: "状态被替换", accent: true},
        {label: "结论", value: "文字保持可编辑"},
      ]}
    />
    <ProcessFlow x={610} y={790} width={1120} labels={["旧状态", "核对证据", "替换结果"]} enterAt={90} />
    <OutlinedSubtitle text="表格、手机和流程进入图解舞台，不烤进生成图" />
    <ForegroundWipe startAt={136} />
  </AbsoluteFill>
);

const ResultScene: React.FC = () => (
  <AbsoluteFill>
    <SceneBackdrop src={ASSETS.backgrounds.serviceShop} />
    <PoseSwap from={ASSETS.characters.otterExplain} to={ASSETS.characters.otterCelebrate} x={90} y={420} width={470} swapAt={78} layer="subjectBack" />
    <SpriteLayer src={ASSETS.characters.beaverHandoff} x={510} y={435} width={455} enterAt={12} fromX={-60} layer="subjectBack" />
    <SpriteLayer src={ASSETS.characters.capybaraReceive} x={1150} y={420} width={485} enterAt={18} fromX={60} layer="subjectBack" />
    <SpriteLayer src={ASSETS.modules.serviceCounter} x={680} y={360} width={760} enterAt={0} fromY={28} layer="occluder" />
    <PropContact src={ASSETS.props.parcel} from={{x: 795, y: 570}} to={{x: 1080, y: 570}} width={235} startAt={38} duration={42} />
    <OutlinedSubtitle text="姿态替换、道具接触和结果落位共同完成叙事" />
    <ForegroundWipe startAt={136} />
  </AbsoluteFill>
);

export const CollageKnowledgeVideo: React.FC = () => (
  <AbsoluteFill style={{background: COLORS.deep, fontFamily: "PingFang SC, Noto Sans CJK SC, sans-serif"}}>
    <Sequence durationInFrames={60} premountFor={20}>
      <TypewriterCard text="变化必须发生在关系里" />
    </Sequence>
    <Sequence from={60} durationInFrames={150} premountFor={30}>
      <ProblemScene />
    </Sequence>
    <Sequence from={210} durationInFrames={150} premountFor={30}>
      <DiagramScene />
    </Sequence>
    <Sequence from={360} durationInFrames={150} premountFor={30}>
      <ResultScene />
    </Sequence>
  </AbsoluteFill>
);
