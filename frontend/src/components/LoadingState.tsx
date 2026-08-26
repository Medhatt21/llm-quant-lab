interface LoadingStateProps {
  message?: string;
}

export default function LoadingState({ message = 'Loading...' }: LoadingStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <div className="spinner-dm mb-5" />
      <p className="text-[11px] text-[#999] tracking-[0.1em] uppercase font-medium">{message}</p>
    </div>
  );
}
