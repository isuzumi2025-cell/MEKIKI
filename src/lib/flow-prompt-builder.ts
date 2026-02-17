/**
 * flow-prompt-builder.ts
 *
 * FlowShot プロンプトビルダー — 動画生成用のプロンプト構造を定義・構築する。
 * キャラクター・オブジェクト・カメラワーク等のメタデータから
 * Veo 最適化プロンプトを生成する。
 *
 * FlowForge SDK — Prompt Layer
 */

export interface CharacterDetail {
    name: string;
    role?: string;
    appearance: string;
    clothing?: string;
    action?: string;
    position?: string;
}

export interface ObjectDetail {
    name: string;
    description: string;
    material?: string;
    color?: string;
    scale?: string;
    position?: string;
    keyFeatures?: string[];
}

export interface ToneMannerConfig {
    mood: string;
    colorGrading?: string;
    filmStyle?: string;
    era?: string;
}

export interface MotionGraphicsConfig {
    type: string;
    content: string;
    position?: string;
    animation?: string;
}

export type ShotSize =
    | "extreme_wide"
    | "wide"
    | "medium_wide"
    | "medium"
    | "medium_close"
    | "close_up"
    | "extreme_close_up";

export type CameraMovement =
    | "static"
    | "pan_left"
    | "pan_right"
    | "tilt_up"
    | "tilt_down"
    | "dolly_in"
    | "dolly_out"
    | "tracking"
    | "crane"
    | "handheld"
    | "orbit";

export type CameraAngle =
    | "eye_level"
    | "low_angle"
    | "high_angle"
    | "birds_eye"
    | "dutch_angle"
    | "over_the_shoulder";

export interface FlowShot {
    subject: string;
    action?: string;
    setting?: string;
    characters?: CharacterDetail[];
    objects?: ObjectDetail[];
    camera?: CameraMovement;
    angle?: CameraAngle;
    shotSize?: ShotSize;
    lighting?: string;
    toneManner?: ToneMannerConfig;
    motionGraphics?: MotionGraphicsConfig;
    duration?: number;
    style?: string;
    negativePrompt?: string;
}

export class FlowPromptBuilder {
    private shot: FlowShot;

    constructor(subject: string) {
        this.shot = { subject };
    }

    setAction(action: string): this {
        this.shot.action = action;
        return this;
    }

    setSetting(setting: string): this {
        this.shot.setting = setting;
        return this;
    }

    addCharacter(character: CharacterDetail): this {
        if (!this.shot.characters) {
            this.shot.characters = [];
        }
        this.shot.characters.push(character);
        return this;
    }

    addObject(object: ObjectDetail): this {
        if (!this.shot.objects) {
            this.shot.objects = [];
        }
        this.shot.objects.push(object);
        return this;
    }

    setCamera(camera: CameraMovement): this {
        this.shot.camera = camera;
        return this;
    }

    setAngle(angle: CameraAngle): this {
        this.shot.angle = angle;
        return this;
    }

    setShotSize(size: ShotSize): this {
        this.shot.shotSize = size;
        return this;
    }

    setLighting(lighting: string): this {
        this.shot.lighting = lighting;
        return this;
    }

    setToneManner(config: ToneMannerConfig): this {
        this.shot.toneManner = config;
        return this;
    }

    setMotionGraphics(config: MotionGraphicsConfig): this {
        this.shot.motionGraphics = config;
        return this;
    }

    setDuration(seconds: number): this {
        this.shot.duration = seconds;
        return this;
    }

    setStyle(style: string): this {
        this.shot.style = style;
        return this;
    }

    setNegativePrompt(prompt: string): this {
        this.shot.negativePrompt = prompt;
        return this;
    }

    build(): FlowShot {
        return { ...this.shot };
    }

    buildPrompt(): string {
        const parts: string[] = [];

        if (this.shot.shotSize) {
            parts.push(`${formatShotSize(this.shot.shotSize)} shot`);
        }

        parts.push(this.shot.subject);

        if (this.shot.action) {
            parts.push(this.shot.action);
        }

        if (this.shot.characters?.length) {
            const charDescs = this.shot.characters.map(c => describeCharacter(c));
            parts.push(charDescs.join(". "));
        }

        if (this.shot.objects?.length) {
            const objDescs = this.shot.objects.map(o => describeObject(o));
            parts.push(objDescs.join(". "));
        }

        if (this.shot.setting) {
            parts.push(`set in ${this.shot.setting}`);
        }

        if (this.shot.camera) {
            parts.push(`${formatCameraMovement(this.shot.camera)} camera movement`);
        }

        if (this.shot.angle) {
            parts.push(`${formatCameraAngle(this.shot.angle)} angle`);
        }

        if (this.shot.lighting) {
            parts.push(this.shot.lighting);
        }

        if (this.shot.toneManner) {
            const tm = this.shot.toneManner;
            const tmParts = [tm.mood];
            if (tm.colorGrading) tmParts.push(tm.colorGrading);
            if (tm.filmStyle) tmParts.push(tm.filmStyle);
            if (tm.era) tmParts.push(`${tm.era} era`);
            parts.push(tmParts.join(", "));
        }

        if (this.shot.style) {
            parts.push(this.shot.style);
        }

        return parts.join(". ") + ".";
    }
}

function describeCharacter(c: CharacterDetail): string {
    const parts = [c.name];
    if (c.role) parts.push(`(${c.role})`);
    parts.push(c.appearance);
    if (c.clothing) parts.push(`wearing ${c.clothing}`);
    if (c.action) parts.push(c.action);
    if (c.position) parts.push(`positioned ${c.position}`);
    return parts.join(", ");
}

function describeObject(o: ObjectDetail): string {
    const parts = [o.name];
    parts.push(o.description);
    if (o.material) parts.push(`made of ${o.material}`);
    if (o.color) parts.push(o.color);
    if (o.scale) parts.push(`${o.scale} scale`);
    if (o.position) parts.push(`at ${o.position}`);
    return parts.join(", ");
}

function formatShotSize(size: ShotSize): string {
    const map: Record<ShotSize, string> = {
        extreme_wide: "Extreme wide",
        wide: "Wide",
        medium_wide: "Medium wide",
        medium: "Medium",
        medium_close: "Medium close-up",
        close_up: "Close-up",
        extreme_close_up: "Extreme close-up",
    };
    return map[size];
}

function formatCameraMovement(movement: CameraMovement): string {
    const map: Record<CameraMovement, string> = {
        static: "Static",
        pan_left: "Pan left",
        pan_right: "Pan right",
        tilt_up: "Tilt up",
        tilt_down: "Tilt down",
        dolly_in: "Dolly in",
        dolly_out: "Dolly out",
        tracking: "Tracking",
        crane: "Crane",
        handheld: "Handheld",
        orbit: "Orbit",
    };
    return map[movement];
}

function formatCameraAngle(angle: CameraAngle): string {
    const map: Record<CameraAngle, string> = {
        eye_level: "Eye level",
        low_angle: "Low",
        high_angle: "High",
        birds_eye: "Bird's eye",
        dutch_angle: "Dutch",
        over_the_shoulder: "Over the shoulder",
    };
    return map[angle];
}
