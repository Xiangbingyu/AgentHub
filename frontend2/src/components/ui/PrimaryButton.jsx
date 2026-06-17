import './PrimaryButton.css';

export default function PrimaryButton({
  children,
  className = '',
  icon: Icon,
  size = 14,
  ...props
}) {
  const classes = ['primary-button', className].filter(Boolean).join(' ');

  return (
    <button type="button" className={classes} {...props}>
      {Icon ? <Icon size={size} /> : null}
      {children}
    </button>
  );
}
