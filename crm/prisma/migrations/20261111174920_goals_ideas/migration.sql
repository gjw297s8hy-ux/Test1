-- CreateEnum
CREATE TYPE "CampaignGoal" AS ENUM ('CLIENTS', 'SUBCONTRACTING', 'OUTLETS', 'PARTNERS');

-- AlterEnum
ALTER TYPE "RunType" ADD VALUE 'IDEAS';

-- AlterTable
ALTER TABLE "Campaign" ADD COLUMN     "goal" "CampaignGoal" NOT NULL DEFAULT 'CLIENTS';

-- CreateTable
CREATE TABLE "Idea" (
    "id" TEXT NOT NULL,
    "orgId" TEXT NOT NULL,
    "goal" "CampaignGoal" NOT NULL,
    "title" TEXT NOT NULL,
    "why" TEXT NOT NULL,
    "industry" TEXT NOT NULL DEFAULT '',
    "location" TEXT NOT NULL DEFAULT '',
    "size" TEXT NOT NULL DEFAULT '',
    "roles" TEXT NOT NULL DEFAULT '',
    "keywords" TEXT NOT NULL DEFAULT '',
    "pitch" TEXT NOT NULL DEFAULT '',
    "usedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Idea_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Idea_orgId_createdAt_idx" ON "Idea"("orgId", "createdAt");

-- AddForeignKey
ALTER TABLE "Idea" ADD CONSTRAINT "Idea_orgId_fkey" FOREIGN KEY ("orgId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;
