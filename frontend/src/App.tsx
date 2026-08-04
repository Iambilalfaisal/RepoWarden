import { useRef } from "react"
import { ChatPane } from "@/components/chat/ChatPane"
import { CodeWorkspace, type CodeWorkspaceHandle } from "@/components/workspace/CodeWorkspace"
import { OpenDirectory } from "@/components/workspace/OpenDirectory"
import { useAgentChat } from "@/hooks/useAgentChat"
import { useWorkspace } from "@/hooks/useWorkspace"

function App() {
  const workspace = useWorkspace()
  const workspaceRef = useRef<CodeWorkspaceHandle>(null)

  const {
    messages,
    isHydrating,
    isStreaming,
    awaitingAuthorization,
    pendingApprovals,
    writtenFiles,
    proposedEdits,
    sendMessage,
    authorize,
    reject,
    decideFile,
  } = useAgentChat({
    rootDir: workspace.rootDir,
    onFileWritten: (edit) => {
      workspace.updateFileCache(edit.file_name, edit.proposed_code)
      void workspace.refreshTree()
    },
  })

  const handleJumpToLine = (fileName: string, line: number) => {
    workspace.setActiveFile(fileName)
    // Let the file switch / content fetch flush before scrolling to the line.
    requestAnimationFrame(() => workspaceRef.current?.revealLine(line))
  }

  if (!workspace.rootDir || !workspace.tree) {
    return (
      <OpenDirectory
        onOpen={workspace.openRoot}
        isOpening={workspace.isOpening}
        error={workspace.openError}
      />
    )
  }

  return (
    <div className="grid h-screen grid-cols-[minmax(360px,1fr)_2fr] overflow-hidden">
      <ChatPane
        messages={messages}
        isHydrating={isHydrating}
        isStreaming={isStreaming}
        awaitingAuthorization={awaitingAuthorization}
        pendingApprovals={pendingApprovals}
        onSend={sendMessage}
        onAllow={authorize}
        onReject={reject}
        onDecideFile={decideFile}
        onJumpToLine={handleJumpToLine}
        onViewFile={workspace.setActiveFile}
      />
      <CodeWorkspace
        ref={workspaceRef}
        tree={workspace.tree}
        activeFile={workspace.activeFile}
        onSelectFile={workspace.setActiveFile}
        fileContent={workspace.fileContent}
        isFileLoading={workspace.isFileLoading}
        writtenFiles={writtenFiles}
        proposedEdits={proposedEdits}
      />
    </div>
  )
}

export default App
