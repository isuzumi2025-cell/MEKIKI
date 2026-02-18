/**
 * strategy-manager.ts
 *
 * 生成戦略の自動選択・実行を行うマネージャー。
 * 登録されたストラテジーの中から、与えられたコンテキストに最適なものを自動選択して実行する。
 */

import type {
  GenerationContext,
  GenerationResult,
  GenerationStrategy,
} from "./strategies/generation-strategy.js";

export class StrategyManager {
  private strategies: GenerationStrategy[] = [];

  register(strategy: GenerationStrategy): this {
    this.strategies.push(strategy);
    return this;
  }

  getStrategies(): readonly GenerationStrategy[] {
    return this.strategies;
  }

  selectStrategy(context: GenerationContext): GenerationStrategy | null {
    for (const strategy of this.strategies) {
      if (strategy.canHandle(context)) {
        return strategy;
      }
    }
    return null;
  }

  async execute(context: GenerationContext): Promise<GenerationResult> {
    const strategy = this.selectStrategy(context);

    if (!strategy) {
      const supportedTypes = this.strategies.flatMap(
        (s) => [...s.supportedInputTypes]
      );
      const uniqueTypes = [...new Set(supportedTypes)];

      return {
        success: false,
        outputType: "image",
        error:
          `入力タイプ "${context.inputType}" を処理できるストラテジーがありません。` +
          `登録済みストラテジー: ${this.strategies.map((s) => s.name).join(", ") || "なし"}。` +
          `対応入力タイプ: ${uniqueTypes.join(", ") || "なし"}`,
        strategyName: "none",
      };
    }

    return strategy.execute(context);
  }
}
