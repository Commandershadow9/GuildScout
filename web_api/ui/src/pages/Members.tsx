import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Users, Search, Download, ChevronLeft, ChevronRight, Loader2, AlertCircle, Trophy, MessageSquare, Mic, Calendar, SortAsc, SortDesc } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MemberEntry {
  rank: number;
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

interface RankingsData {
  rankings: MemberEntry[];
  total: number;
  page: number;
  per_page: number;
  weights?: {
    days: number;
    messages: number;
    voice: number;
  };
}

interface MembersProps {
  data: {
    guild: { id: string; name: string };  // String for JavaScript BigInt safety
  };
}

type SortField = 'rank' | 'final_score' | 'message_count' | 'voice_minutes' | 'days_in_server';

const Members: React.FC<MembersProps> = ({ data }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rankings, setRankings] = useState<RankingsData | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('rank');
  const [sortAsc, setSortAsc] = useState(true);

  const perPage = 25;

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const offset = (page - 1) * perPage;
      const response = await fetch(
        `/api/guilds/${data.guild.id}/analytics/rankings?limit=${perPage}&offset=${offset}`
      );
      const json = await response.json();

      if (json.success) {
        setRankings(json.data);
      } else {
        throw new Error(json.error || 'Failed to load members');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [data.guild.id, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleExport = () => {
    if (!rankings) return;

    const headers = ['Rank', 'User', 'Score', 'Messages', 'Voice (min)', 'Days'];
    const rows = rankings.rankings.map(r => [
      r.rank,
      r.display_name,
      r.final_score,
      r.message_count,
      r.voice_minutes,
      r.days_in_server
    ]);

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `guildscout_members_${data.guild.name}_page${page}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === 'rank');
    }
  };

  // Client-side sorting of current page data
  const sortedRankings = rankings?.rankings ? [...rankings.rankings].sort((a, b) => {
    let comparison = 0;
    switch (sortField) {
      case 'rank':
        comparison = a.rank - b.rank;
        break;
      case 'final_score':
        comparison = b.final_score - a.final_score;
        break;
      case 'message_count':
        comparison = b.message_count - a.message_count;
        break;
      case 'voice_minutes':
        comparison = b.voice_minutes - a.voice_minutes;
        break;
      case 'days_in_server':
        comparison = b.days_in_server - a.days_in_server;
        break;
    }
    return sortAsc ? comparison : -comparison;
  }) : [];

  // Client-side search filtering
  const filteredRankings = search
    ? sortedRankings.filter(m =>
        m.display_name.toLowerCase().includes(search.toLowerCase())
      )
    : sortedRankings;

  const totalPages = rankings ? Math.ceil(rankings.total / perPage) : 0;

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return sortAsc ? <SortAsc className="h-3 w-3" /> : <SortDesc className="h-3 w-3" />;
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-heading font-bold tracking-tight text-white flex items-center gap-3">
            <Users className="h-6 w-6 md:h-8 md:w-8 text-[var(--primary)]" />
            Member Rankings
          </h1>
          <p className="text-[var(--muted)] mt-1 text-sm md:text-base">
            {rankings ? `${rankings.total} members ranked` : 'Loading...'}
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 sm:flex-initial">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted)]" />
            <input
              type="text"
              placeholder="Search members..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full sm:w-48 pl-10 pr-4 py-3 sm:py-2 bg-[var(--surface-2)] border border-[var(--border)] rounded-lg text-white text-sm focus:ring-2 focus:ring-[var(--primary)]/50 focus:border-[var(--primary)] outline-none"
            />
          </div>

          {/* Export */}
          <button
            onClick={handleExport}
            disabled={!rankings}
            className="flex items-center justify-center gap-2 bg-[var(--surface-2)] text-white px-4 py-3 sm:py-2 rounded-lg font-bold border border-[var(--border)] hover:bg-[var(--bg-1)] transition-all text-sm disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            <span className="sm:inline">Export</span>
          </button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="panel-glass p-6 border-l-4 border-[var(--danger)]">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-[var(--danger)]" />
            <p className="text-[var(--danger)]">{error}</p>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-[var(--primary)]" />
        </div>
      )}

      {/* Table */}
      {!loading && rankings && (
        <div className="panel-glass p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--surface-2)] text-[var(--muted)] text-xs uppercase">
                <tr>
                  <th
                    className="px-3 md:px-4 py-3 text-left cursor-pointer hover:text-white transition-colors"
                    onClick={() => handleSort('rank')}
                  >
                    <div className="flex items-center gap-1">
                      <span className="hidden sm:inline">Rank</span>
                      <span className="sm:hidden">#</span>
                      <SortIcon field="rank" />
                    </div>
                  </th>
                  <th className="px-3 md:px-4 py-3 text-left">Member</th>
                  <th
                    className="px-3 md:px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                    onClick={() => handleSort('final_score')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Score <SortIcon field="final_score" />
                    </div>
                  </th>
                  <th
                    className="hidden md:table-cell px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                    onClick={() => handleSort('message_count')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      <MessageSquare className="h-3 w-3" /> Messages <SortIcon field="message_count" />
                    </div>
                  </th>
                  <th
                    className="hidden lg:table-cell px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                    onClick={() => handleSort('voice_minutes')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      <Mic className="h-3 w-3" /> Voice <SortIcon field="voice_minutes" />
                    </div>
                  </th>
                  <th
                    className="hidden sm:table-cell px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                    onClick={() => handleSort('days_in_server')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      <Calendar className="h-3 w-3" /> Days <SortIcon field="days_in_server" />
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {filteredRankings.length > 0 ? (
                  filteredRankings.map((member) => (
                    <tr key={member.user_id} className="hover:bg-[var(--bg-1)] transition-colors">
                      <td className="px-3 md:px-4 py-3">
                        <span className={cn(
                          "font-mono font-bold text-sm",
                          member.rank === 1 && "text-yellow-400",
                          member.rank === 2 && "text-gray-300",
                          member.rank === 3 && "text-amber-600",
                          member.rank > 3 && member.rank <= 10 && "text-[var(--primary)]",
                          member.rank > 10 && "text-[var(--muted)]"
                        )}>
                          {member.rank <= 3 && (
                            <span className="mr-1">
                              {member.rank === 1 && '🥇'}
                              {member.rank === 2 && '🥈'}
                              {member.rank === 3 && '🥉'}
                            </span>
                          )}
                          #{member.rank}
                        </span>
                      </td>
                      <td className="px-3 md:px-4 py-3">
                        <span className="font-medium text-white text-sm truncate max-w-[120px] md:max-w-none block">{member.display_name}</span>
                      </td>
                      <td className="px-3 md:px-4 py-3 text-right">
                        <span className="font-mono text-[var(--primary)] font-bold text-sm">
                          {member.final_score.toFixed(1)}
                        </span>
                      </td>
                      <td className="hidden md:table-cell px-4 py-3 text-right text-[var(--muted)] text-sm">
                        {member.message_count.toLocaleString()}
                      </td>
                      <td className="hidden lg:table-cell px-4 py-3 text-right text-[var(--muted)] text-sm">
                        {member.voice_minutes.toLocaleString()} min
                      </td>
                      <td className="hidden sm:table-cell px-4 py-3 text-right text-[var(--muted)] text-sm">
                        {member.days_in_server}d
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-[var(--muted)]">
                      {search ? 'No members match your search' : 'No member data available'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="px-4 py-3 border-t border-[var(--border)] bg-[var(--surface-2)] flex items-center justify-between">
              <p className="text-xs sm:text-sm text-[var(--muted)]">
                <span className="hidden sm:inline">Page </span>{page}<span className="hidden sm:inline"> of</span><span className="sm:hidden">/</span> {totalPages}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-3 sm:p-2 rounded-lg bg-[var(--bg-0)] border border-[var(--border)] hover:bg-[var(--bg-1)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors active:scale-95"
                >
                  <ChevronLeft className="h-5 w-5 sm:h-4 sm:w-4" />
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="p-3 sm:p-2 rounded-lg bg-[var(--bg-0)] border border-[var(--border)] hover:bg-[var(--bg-1)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors active:scale-95"
                >
                  <ChevronRight className="h-5 w-5 sm:h-4 sm:w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Scoring Info */}
      {rankings?.weights && (
        <div className="panel-glass p-4">
          <p className="text-sm text-[var(--muted)]">
            <Trophy className="h-4 w-4 inline mr-2 text-[var(--warning)]" />
            <strong>Scoring:</strong>{' '}
            Days ({(rankings.weights.days * 100).toFixed(0)}%) +
            Messages ({(rankings.weights.messages * 100).toFixed(0)}%) +
            Voice ({(rankings.weights.voice * 100).toFixed(0)}%)
          </p>
        </div>
      )}
    </div>
  );
};

export default Members;
