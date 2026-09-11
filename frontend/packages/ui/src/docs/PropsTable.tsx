import "./PropsTable.css";


export interface PropDefinition {
  name: string;
  type: string;
  defaultValue?: string;
  description?: string;
}


export interface PropsTableProps {
  props: PropDefinition[];
}


export function PropsTable({
  props,
}: PropsTableProps) {

  return (
    <table className="props-table">

      <thead>

        <tr>

          <th>
            Prop
          </th>

          <th>
            Type
          </th>

          <th>
            Default
          </th>

          <th>
            Description
          </th>

        </tr>

      </thead>


      <tbody>

        {
          props.map((prop) => (

            <tr
              key={prop.name}
            >

              <td>
                {prop.name}
              </td>


              <td>
                {prop.type}
              </td>


              <td>
                {prop.defaultValue ?? "-"}
              </td>


              <td>
                {prop.description ?? "-"}
              </td>


            </tr>

          ))
        }

      </tbody>

    </table>
  );
}