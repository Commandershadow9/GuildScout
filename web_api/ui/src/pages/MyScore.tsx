import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Trophy, MessageSquare, Mic, Calendar, Loader2, AlertCircle, TrendingUp, Target } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ScoreData {
  rank: number;
  total_members: number;
  percentile: number;
  user_id: string;
  display_name: string;
  final_score: number;
  days_score: number;
  message_score: number;
  voice_score: number;
  message_count: number;
  voice_minutes: number;
  days_in_server: number;
}

interface MyScoreProps {
  data: {
    guild: { id: string; name: string };  // String for JavaScript BigInt safety
    session: { username: string; avatar: string; user_id: string };  // String for BigInt safety
    avatar_url: string;
  };
}

const MyScore: React.FC<MyScoreProps> = ({ data }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [score, setScore] = useState<ScoreData | null>(null);

  useEffect(() => {
    const fetchScore = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(`/api/guilds/${data.guild.id}/my-score`);
        const json = await response.json();

        if (json.success) {
          setScore(json.data);
        } else {
          throw new Error(json.error || 'Failed to load score');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchScore();
  }, [data.guild.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[500px]">
        <div className="text-center">
          <Loader2 className="h-10 w-10 animate-spin text-[var(--primary)] mx-auto mb-4" />
          <p className="text-[var(--muted)]">Loading your score...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[500px]">
        <div className="text-center max-w-md">
          <AlertCircle className="h-12 w-12 text-[var(--danger)] mx-auto mb-4" />
          <p className="text-[var(--danger)] font-bold mb-2 text-lg">Unable to Load Score</p>
          <p className="text-[var(--muted)]">{error}</p>
          <p className="text-[var(--muted)] text-sm mt-4">
            Make sure you are a member of this server and the bot has tracked your activity.
          </p>
        </div>
      </div>
    );
  }

  if (!score) {
    return (
      <div className="flex items-center justify-center min-h-[500px]">
        <div className="text-center">
          <Target className="h-12 w-12 text-[var(--muted)] mx-auto mb-4" />
          <p className="text-white font-bold mb-2 text-lg">No Score Data</p>
          <p className="text-[var(--muted)]">
            Your activity hasn't been tracked yet. Start chatting and using voice channels!
          </p>
        </div>
      </div>
    );
  }

  // Determine rank color and emoji
  const getRankDisplay = () => {
    if (score.rank === 1) return { emoji: '🥇', color: 'text-yellow-400', label: 'Gold' };
    if (score.rank === 2) return { emoji: '🥈', color: 'text-gray-300', label: 'Silver' };
    if (score.rank === 3) return { emoji: '🥉', color: 'text-amber-600', label: 'Bronze' };
    if (score.rank <= 10) return { emoji: '🏆', color: 'text-[var(--primary)]', label: 'Top 10' };
    if (score.rank <= 25) return { emoji: '⭐', color: 'text-[var(--warning)]', label: 'Top 25' };
    return { emoji: '📊', color: 'text-[var(--muted)]', label: '' };
  };

  const rankDisplay = getRankDisplay();

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-heading font-bold tracking-tight text-white">
          Your Ranking Score
        </h1>
        <p className="text-[var(--muted)] mt-2">
          {data.guild.name}
        </p>
      </div>

      {/* Main Score Card */}
      <div className="panel-glass p-8 relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-[var(--primary)]/5 rounded-full blur-3xl -mr-32 -mt-32" />

        <div className="relative flex flex-col md:flex-row items-center gap-8">
          {/* Avatar and Rank */}
          <div className="text-center">
            <div className="relative inline-block">
              <img
                src={data.avatar_url}
                alt={data.session.username}
                className="w-24 h-24 rounded-full border-4 border-[var(--primary)]"
              />
              <div className="absolute -bottom-2 -right-2 w-10 h-10 bg-[var(--surface-2)] rounded-full flex items-center justify-center border-2 border-[var(--border)] text-2xl">
                {rankDisplay.emoji}
              </div>
            </div>
            <p className="mt-4 font-bold text-white text-lg">{data.session.username}</p>
          </div>

          {/* Score Display */}
          <div className="flex-1 text-center md:text-left">
            <div className="mb-4">
              <p className="text-sm text-[var(--muted)] uppercase tracking-wider mb-1">Final Score</p>
              <p className="text-6xl font-bold text-[var(--primary)] font-mono">
                {score.final_score.toFixed(1)}
              </p>
            </div>

            <div className="flex flex-wrap gap-4 justify-center md:justify-start">
              <div className="bg-[var(--bg-0)] px-4 py-2 rounded-lg">
                <p className="text-xs text-[var(--muted)]">Rank</p>
                <p className={cn("text-xl font-bold", rankDisplay.color)}>
                  #{score.rank}
                </p>
              </div>
              <div className="bg-[var(--bg-0)] px-4 py-2 rounded-lg">
                <p className="text-xs text-[var(--muted)]">of</p>
                <p className="text-xl font-bold text-white">
                  {score.total_members}
                </p>
              </div>
              <div className="bg-[var(--bg-0)] px-4 py-2 rounded-lg">
                <p className="text-xs text-[var(--muted)]">Percentile</p>
                <p className="text-xl font-bold text-[var(--success)]">
                  Top {(100 - score.percentile).toFixed(0)}%
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Score Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ScoreBreakdownCard
          icon={Calendar}
          title="Membership"
          value={score.days_in_server}
          unit="days"
          score={score.days_score}
          color="warning"
          description="Time spent as a member"
        />
        <ScoreBreakdownCard
          icon={MessageSquare}
          title="Messages"
          value={score.message_count}
          unit="sent"
          score={score.message_score}
          color="primary"
          description="Total messages tracked"
        />
        <ScoreBreakdownCard
          icon={Mic}
          title="Voice Activity"
          value={score.voice_minutes}
          unit="min"
          score={score.voice_score}
          color="secondary"
          description="Time in voice channels"
        />
      </div>

      {/* Score Progress Bars */}
      <div className="panel-glass p-6">
        <h3 className="font-bold text-white mb-6 flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-[var(--primary)]" />
          Score Breakdown
        </h3>

        <div className="space-y-6">
          <ScoreBar label="Days in Server" score={score.days_score} color="warning" />
          <ScoreBar label="Message Activity" score={score.message_score} color="primary" />
          <ScoreBar label="Voice Activity" score={score.voice_score} color="secondary" />
        </div>

        <div className="mt-6 pt-4 border-t border-[var(--border)]">
          <p className="text-sm text-[var(--muted)]">
            Scores are normalized (0-100) based on the most active members.
            Your final score is a weighted combination of all three metrics.
          </p>
        </div>
      </div>

      {/* Tips */}
      <div className="panel-glass p-6 border-l-4 border-[var(--primary)]">
        <h3 className="font-bold text-white mb-2">How to Improve Your Score</h3>
        <ul className="text-[var(--muted)] text-sm space-y-1">
          <li>• Be active in text channels - every message counts!</li>
          <li>• Join voice channels regularly to boost your voice activity score</li>
          <li>• Long-term membership is rewarded - stay active over time</li>
        </ul>
      </div>
    </div>
  );
};

interface ScoreBreakdownCardProps {
  icon: React.ElementType;
  title: string;
  value: number;
  unit: string;
  score: number;
  color: 'primary' | 'secondary' | 'warning';
  description: string;
}

const ScoreBreakdownCard: React.FC<ScoreBreakdownCardProps> = ({
  icon: Icon,
  title,
  value,
  unit,
  score,
  color,
  description,
}) => {
  const colorClasses = {
    primary: 'text-[var(--primary)] bg-[var(--primary)]/10',
    secondary: 'text-[var(--secondary)] bg-[var(--secondary)]/10',
    warning: 'text-[var(--warning)] bg-[var(--warning)]/10',
  };

  return (
    <div className="panel-glass p-6">
      <div className="flex items-start gap-4">
        <div className={cn("p-3 rounded-lg", colorClasses[color])}>
          <Icon className="h-6 w-6" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-[var(--muted)]">{title}</p>
          <p className="text-2xl font-bold text-white">
            {value.toLocaleString()} <span className="text-sm text-[var(--muted)]">{unit}</span>
          </p>
          <p className="text-xs text-[var(--muted)] mt-1">{description}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-[var(--muted)]">Score</p>
          <p className={cn("text-xl font-bold font-mono", colorClasses[color].split(' ')[0])}>
            {score.toFixed(0)}
          </p>
        </div>
      </div>
    </div>
  );
};

interface ScoreBarProps {
  label: string;
  score: number;
  color: 'primary' | 'secondary' | 'warning';
}

const ScoreBar: React.FC<ScoreBarProps> = ({ label, score, color }) => {
  const bgColors = {
    primary: 'bg-[var(--primary)]',
    secondary: 'bg-[var(--secondary)]',
    warning: 'bg-[var(--warning)]',
  };

  return (
    <div>
      <div className="flex justify-between mb-2">
        <span className="text-sm font-medium text-white">{label}</span>
        <span className="text-sm font-mono text-[var(--muted)]">{score.toFixed(1)}/100</span>
      </div>
      <div className="h-3 bg-[var(--bg-0)] rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", bgColors[color])}
          style={{ width: `${Math.min(100, score)}%` }}
        />
      </div>
    </div>
  );
};

export default MyScore;
