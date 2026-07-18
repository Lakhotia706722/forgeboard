/**
 * Kanban board placeholder — fully implemented in Phase 5.
 */
export default function BoardPage() {
  const lanes = ['Draft', 'Testing', 'Live', 'Paused', 'Needs Review']

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <h1 className="text-2xl font-bold mb-6">Agent Board</h1>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {lanes.map((lane) => (
          <div
            key={lane}
            className="min-w-[220px] bg-gray-900 border border-gray-800 rounded-xl p-4"
          >
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
              {lane}
            </h2>
            <div className="text-xs text-gray-700 text-center py-8">
              Phase 5
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
