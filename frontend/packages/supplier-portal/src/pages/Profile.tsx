import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "react-toastify";

const profileSchema = z.object({
  companyName: z
    .string()
    .trim()
    .min(1, "Company name is required."),

  contactName: z
    .string()
    .trim()
    .min(
      2,
      "Contact name must be at least 2 characters."
    ),

  email: z
    .string()
    .trim()
    .min(1, "Email is required.")
    .email("Enter a valid email address."),

  phone: z
    .string()
    .trim()
    .min(
      10,
      "Phone number must be at least 10 digits."
    )
    .regex(
      /^[0-9+\-\s()]+$/,
      "Enter a valid phone number."
    ),

  notifications: z.boolean(),
});

type ProfileFormValues = z.infer<typeof profileSchema>;

const Profile = () => {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),

    defaultValues: {
      companyName: "ABC Supplies Pvt Ltd",
      contactName: "Supplier Admin",
      email: "supplier@company.com",
      phone: "9876543210",
      notifications: true,
    },
  });

  const onSubmit = async (values: ProfileFormValues) => {
    try {
      // Simulate saving to the backend.
      await new Promise((resolve) =>
        window.setTimeout(resolve, 600)
      );

      reset(values);

      toast.success(
        "Profile updated successfully."
      );
    } catch {
      toast.error(
        "Failed to update profile."
      );
    }
  };

  return (
    <main className="profile-page">
      <h1>Profile & Settings</h1>

      <form
        className="profile-form"
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        {/* Company Name */}
        <div className="profile-field">
          <label htmlFor="companyName">
            Company Name
          </label>

          <input
            id="companyName"
            type="text"
            {...register("companyName")}
            aria-invalid={
              errors.companyName ? "true" : "false"
            }
            aria-describedby={
              errors.companyName
                ? "companyName-error"
                : undefined
            }
          />

          {errors.companyName && (
            <p
              id="companyName-error"
              className="error"
              role="alert"
            >
              {errors.companyName.message}
            </p>
          )}
        </div>

        {/* Contact Name */}
        <div className="profile-field">
          <label htmlFor="contactName">
            Contact Name
          </label>

          <input
            id="contactName"
            type="text"
            {...register("contactName")}
            aria-invalid={
              errors.contactName ? "true" : "false"
            }
            aria-describedby={
              errors.contactName
                ? "contactName-error"
                : undefined
            }
          />

          {errors.contactName && (
            <p
              id="contactName-error"
              className="error"
              role="alert"
            >
              {errors.contactName.message}
            </p>
          )}
        </div>

        {/* Email */}
        <div className="profile-field">
          <label htmlFor="email">
            Email
          </label>

          <input
            id="email"
            type="email"
            {...register("email")}
            aria-invalid={
              errors.email ? "true" : "false"
            }
            aria-describedby={
              errors.email
                ? "email-error"
                : undefined
            }
          />

          {errors.email && (
            <p
              id="email-error"
              className="error"
              role="alert"
            >
              {errors.email.message}
            </p>
          )}
        </div>

        {/* Phone Number */}
        <div className="profile-field">
          <label htmlFor="phone">
            Phone Number
          </label>

          <input
            id="phone"
            type="tel"
            {...register("phone")}
            aria-invalid={
              errors.phone ? "true" : "false"
            }
            aria-describedby={
              errors.phone
                ? "phone-error"
                : undefined
            }
          />

          {errors.phone && (
            <p
              id="phone-error"
              className="error"
              role="alert"
            >
              {errors.phone.message}
            </p>
          )}
        </div>

        {/* Notifications */}
        <label className="notification-setting">
          <input
            type="checkbox"
            {...register("notifications")}
          />

          <span>
            Enable notifications
          </span>
        </label>

        {/* Submit */}
        <button
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting
            ? "Saving..."
            : "Save Changes"}
        </button>
      </form>
    </main>
  );
};

export default Profile;