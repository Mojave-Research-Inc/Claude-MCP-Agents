import { nanoid } from 'nanoid';

// Standard ID generators for different entity types
export const generatePlanId = () => `plan_${nanoid(12)}`;
export const generateStepId = () => `step_${nanoid(12)}`;
export const generateTicketId = () => `tkt_${nanoid(10)}`;
export const generateRouteId = (mcpId: string, tool: string) => `${mcpId}:${tool}`;
export const generateBranchId = () => `branch_${nanoid(10)}`;
export const generateAttestationId = () => `att_${nanoid(12)}`;

// Timestamp utilities
export const now = () => Date.now();
export const futureTimestamp = (offsetMs: number) => Date.now() + offsetMs;