import { logger } from '../logger.js';

export interface MADCandidate {
  id: string;
  solution: any;
  confidence: number;
  rationale: string[];
  cost_estimate: number;
  risk_assessment: number;
  citations?: Array<{ source: string; evidence: string }>;
}

export interface MADEvidence {
  source: string;
  data: any;
  reliability: number;
  timestamp: number;
}

export interface MADJudgment {
  winner: MADCandidate;
  confidence: number;
  rationale: string[];
  debate_rounds: number;
  consensus_score: number;
  minority_opinions?: string[];
}

export class MultiAgentDebateJudge {
  private rounds: number;
  private consensusThreshold: number;

  constructor(rounds: number = 3, consensusThreshold: number = 0.7) {
    this.rounds = rounds;
    this.consensusThreshold = consensusThreshold;
  }

  async judge(candidates: MADCandidate[], evidence: MADEvidence[]): Promise<MADJudgment> {
    logger.info(`Starting MAD judgment with ${candidates.length} candidates`);

    if (candidates.length === 0) {
      throw new Error('No candidates provided for MAD judgment');
    }

    if (candidates.length === 1) {
      return {
        winner: candidates[0],
        confidence: 1.0,
        rationale: ['Single candidate - no debate needed'],
        debate_rounds: 0,
        consensus_score: 1.0
      };
    }

    // Initialize candidate scores
    const candidateScores = new Map<string, number>();
    const candidateSupport = new Map<string, string[]>();

    for (const candidate of candidates) {
      candidateScores.set(candidate.id, this.calculateInitialScore(candidate, evidence));
      candidateSupport.set(candidate.id, []);
    }

    // Conduct debate rounds
    const debateHistory: Array<{ round: number; arguments: any[] }> = [];

    for (let round = 0; round < this.rounds; round++) {
      logger.debug(`MAD round ${round + 1}/${this.rounds}`);

      const roundArguments = await this.conductDebateRound(candidates, evidence, round);
      debateHistory.push({ round: round + 1, arguments: roundArguments });

      // Update scores based on debate arguments
      this.updateScoresFromDebate(candidateScores, candidateSupport, roundArguments);
    }

    // Determine winner and consensus
    const sortedCandidates = Array.from(candidateScores.entries())
      .sort(([, scoreA], [, scoreB]) => scoreB - scoreA);

    const winner = candidates.find(c => c.id === sortedCandidates[0][0])!;
    const winnerScore = sortedCandidates[0][1];
    const runnerUpScore = sortedCandidates[1]?.[1] || 0;

    const consensusScore = this.calculateConsensus(candidateScores);
    const confidence = this.calculateConfidence(winnerScore, runnerUpScore, consensusScore);

    const rationale = this.generateRationale(winner, candidateSupport.get(winner.id) || [], debateHistory);
    const minorityOpinions = this.extractMinorityOpinions(candidates, candidateScores, winner);

    logger.info(`MAD judgment complete: winner ${winner.id} with confidence ${confidence.toFixed(3)}`);

    return {
      winner,
      confidence,
      rationale,
      debate_rounds: this.rounds,
      consensus_score: consensusScore,
      minority_opinions: minorityOpinions
    };
  }

  private calculateInitialScore(candidate: MADCandidate, evidence: MADEvidence[]): number {
    let score = candidate.confidence;

    // Factor in cost (lower is better)
    score -= candidate.cost_estimate * 0.1;

    // Factor in risk (lower is better)
    score -= candidate.risk_assessment * 0.2;

    // Factor in evidence support
    const evidenceSupport = this.calculateEvidenceSupport(candidate, evidence);
    score += evidenceSupport * 0.3;

    return Math.max(0, Math.min(1, score));
  }

  private calculateEvidenceSupport(candidate: MADCandidate, evidence: MADEvidence[]): number {
    if (!candidate.citations || candidate.citations.length === 0) {
      return 0.1; // Low support for uncited claims
    }

    let support = 0;
    let totalWeight = 0;

    for (const citation of candidate.citations) {
      const matchingEvidence = evidence.find(e => e.source === citation.source);
      if (matchingEvidence) {
        const weight = matchingEvidence.reliability;
        support += weight;
        totalWeight += weight;
      }
    }

    return totalWeight > 0 ? support / totalWeight : 0.1;
  }

  private async conductDebateRound(
    candidates: MADCandidate[],
    evidence: MADEvidence[],
    round: number
  ): Promise<any[]> {
    const debateArguments: any[] = [];

    // Each candidate argues against others
    for (let i = 0; i < candidates.length; i++) {
      const advocate = candidates[i];
      const opponents = candidates.filter((_, idx) => idx !== i);

      const argument = await this.generateArgument(advocate, opponents, evidence, round);
      debateArguments.push({
        advocate_id: advocate.id,
        round,
        argument,
        targets: opponents.map(o => o.id)
      });
    }

    return debateArguments;
  }

  private async generateArgument(
    advocate: MADCandidate,
    opponents: MADCandidate[],
    evidence: MADEvidence[],
    round: number
  ): Promise<any> {
    // Simplified argument generation
    const strengths = this.identifyStrengths(advocate, evidence);
    const weaknesses = opponents.map(opp => this.identifyWeaknesses(opp, evidence));

    return {
      strengths,
      opponent_critiques: weaknesses,
      supporting_evidence: advocate.citations || [],
      novelty_claims: this.identifyNoveltyAspects(advocate, opponents),
      round_focus: this.getRoundFocus(round)
    };
  }

  private identifyStrengths(candidate: MADCandidate, evidence: MADEvidence[]): string[] {
    const strengths: string[] = [];

    if (candidate.confidence > 0.8) {
      strengths.push('High confidence in solution viability');
    }

    if (candidate.cost_estimate < 5) {
      strengths.push('Cost-effective approach');
    }

    if (candidate.risk_assessment < 0.3) {
      strengths.push('Low risk profile');
    }

    if (candidate.citations && candidate.citations.length > 2) {
      strengths.push('Well-supported with evidence');
    }

    if (candidate.rationale.length > 3) {
      strengths.push('Comprehensive reasoning provided');
    }

    return strengths;
  }

  private identifyWeaknesses(candidate: MADCandidate, evidence: MADEvidence[]): string[] {
    const weaknesses: string[] = [];

    if (candidate.confidence < 0.5) {
      weaknesses.push('Low confidence in solution');
    }

    if (candidate.cost_estimate > 8) {
      weaknesses.push('High cost estimate');
    }

    if (candidate.risk_assessment > 0.7) {
      weaknesses.push('High risk profile');
    }

    if (!candidate.citations || candidate.citations.length < 2) {
      weaknesses.push('Insufficient evidence support');
    }

    return weaknesses;
  }

  private identifyNoveltyAspects(candidate: MADCandidate, opponents: MADCandidate[]): string[] {
    const novelty: string[] = [];

    // Check for unique approaches
    const candidateKeywords = this.extractKeywords(candidate.solution);
    const opponentKeywords = opponents.flatMap(opp => this.extractKeywords(opp.solution));

    const uniqueKeywords = candidateKeywords.filter(keyword =>
      !opponentKeywords.some(oppKeyword => oppKeyword.toLowerCase() === keyword.toLowerCase())
    );

    if (uniqueKeywords.length > 0) {
      novelty.push(`Unique approach elements: ${uniqueKeywords.join(', ')}`);
    }

    return novelty;
  }

  private extractKeywords(solution: any): string[] {
    if (typeof solution === 'string') {
      return solution.split(/\s+/).filter(word => word.length > 3);
    }

    if (typeof solution === 'object') {
      return Object.values(solution)
        .filter(value => typeof value === 'string')
        .flatMap(str => str.split(/\s+/))
        .filter(word => word.length > 3);
    }

    return [];
  }

  private getRoundFocus(round: number): string {
    const focuses = [
      'Feasibility and technical merit',
      'Cost-effectiveness and resource efficiency',
      'Risk assessment and mitigation strategies'
    ];

    return focuses[round % focuses.length];
  }

  private updateScoresFromDebate(
    candidateScores: Map<string, number>,
    candidateSupport: Map<string, string[]>,
    debateArguments: any[]
  ): void {
    for (const arg of debateArguments) {
      const advocateId = arg.advocate_id;
      const currentScore = candidateScores.get(advocateId) || 0;

      // Boost score based on argument strength
      const strengthBoost = arg.argument.strengths.length * 0.02;
      const evidenceBoost = arg.argument.supporting_evidence.length * 0.01;
      const noveltyBoost = arg.argument.novelty_claims.length * 0.03;

      const totalBoost = strengthBoost + evidenceBoost + noveltyBoost;
      candidateScores.set(advocateId, Math.min(1, currentScore + totalBoost));

      // Record support arguments
      const support = candidateSupport.get(advocateId) || [];
      support.push(...arg.argument.strengths);
      candidateSupport.set(advocateId, support);
    }
  }

  private calculateConsensus(candidateScores: Map<string, number>): number {
    const scores = Array.from(candidateScores.values()).sort((a, b) => b - a);

    if (scores.length < 2) return 1.0;

    const topScore = scores[0];
    const secondScore = scores[1];
    const gap = topScore - secondScore;

    // Higher gap means stronger consensus
    return Math.min(1, gap * 2);
  }

  private calculateConfidence(
    winnerScore: number,
    runnerUpScore: number,
    consensusScore: number
  ): number {
    const scoreGap = winnerScore - runnerUpScore;
    const baseConfidence = winnerScore;

    // Combine base confidence with score gap and consensus
    return (baseConfidence + scoreGap + consensusScore) / 3;
  }

  private generateRationale(
    winner: MADCandidate,
    support: string[],
    debateHistory: Array<{ round: number; arguments: any[] }>
  ): string[] {
    const rationale: string[] = [];

    // Include original rationale
    rationale.push(...winner.rationale);

    // Add debate-derived support
    if (support.length > 0) {
      rationale.push(`Debate analysis: ${support.slice(0, 3).join(', ')}`);
    }

    // Add performance across rounds
    const winnerPerformance = debateHistory
      .flatMap(round => round.arguments)
      .filter(arg => arg.advocate_id === winner.id);

    if (winnerPerformance.length > 0) {
      rationale.push(`Consistent performance across ${winnerPerformance.length} debate rounds`);
    }

    return rationale;
  }

  private extractMinorityOpinions(
    candidates: MADCandidate[],
    candidateScores: Map<string, number>,
    winner: MADCandidate
  ): string[] {
    const minorityOpinions: string[] = [];

    const sortedCandidates = candidates
      .filter(c => c.id !== winner.id)
      .map(c => ({ candidate: c, score: candidateScores.get(c.id) || 0 }))
      .sort((a, b) => b.score - a.score);

    // Include opinions from strong runner-ups
    for (const entry of sortedCandidates.slice(0, 2)) {
      if (entry.score > 0.3) { // Only include substantial alternatives
        minorityOpinions.push(
          `Alternative approach (${entry.candidate.id}): ${entry.candidate.rationale[0] || 'Different strategy'}`
        );
      }
    }

    return minorityOpinions;
  }
}

export const madJudge = new MultiAgentDebateJudge();