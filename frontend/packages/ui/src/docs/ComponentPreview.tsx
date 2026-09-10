import type { ReactNode } from "react";
import "./ComponentPreview.css";


export interface ComponentPreviewProps {
  title: string;

  description?: string;

  children: ReactNode;
}


export function ComponentPreview({
  title,
  description,
  children,
}: ComponentPreviewProps) {

  return (
    <section className="component-preview">

      <div className="component-preview-header">

        <h2 className="component-preview-title">
          {title}
        </h2>


        {description && (
          <p className="component-preview-description">
            {description}
          </p>
        )}

      </div>


      <div className="component-preview-content">

        {children}

      </div>


    </section>
  );
}