import { colors } from "../tokens";

const ErrorState = () => {
  return (
    <div
      style={{
        padding: 30,
        textAlign: "center",
        color: colors.danger,
      }}
    >
      Something went wrong.
    </div>
  );
};

export default ErrorState;